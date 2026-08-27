import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from routeros_api import RouterOsApiPool

from network_management.models.router_management_model import Router
from network_management.services.hotspot_provisioning import _parse_routeros_duration_seconds
from network_management.utils.router_guard import ensure_router_manages_hotspot_users, RouterNotManagedError
from service_operations.models.subscription_models import Subscription

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Expiry enforcement for hotspot accounts. Host-cron command (no Celery worker "
        "runs in this deployment) - same pattern as sample_wan/sample_router_stats: "
        "run this from the OS crontab, not a Celery beat schedule.\n\n"
        "For each manages_hotspot_users=True router, reads /ip/hotspot/user and "
        "/ip/hotspot/active and, per account (grouped by router + username - "
        "usernames are reused across repeat purchases, so one router account can map "
        "to several Subscription rows):\n"
        "  - every mapped subscription's validity window (end_date) has passed -> "
        "kick any live session, delete the /ip/hotspot/user entry (unused connected-time "
        "allowance is forfeit), mark lapsed 'active' subscriptions 'expired'.\n"
        "  - connected-time allowance exhausted (uptime >= limit-uptime) but at least "
        "one mapped window is still open -> make sure it's disconnected (kick if "
        "RouterOS hasn't already), leave the entry alone - a repurchase's carry-over "
        "reconciliation (see hotspot_provisioning.provision_hotspot_user) needs its "
        "counters intact.\n"
        "  - any mapped subscription is 'pending_activation' (paid, not yet "
        "successfully provisioned) -> never touched, regardless of window state - the "
        "reconcile_payments safety-net retry owes that customer service.\n\n"
        "Also marks any 'active' subscription whose own end_date has passed 'expired', "
        "independent of what happens to the router account it maps to - this is what "
        "makes 'does this person have live time?' answerable from the database alone."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--live',
            action='store_true',
            help=(
                "Actually delete/disconnect on the router and write status changes to "
                "the database. Without this flag (the default) the command runs in "
                "dry-run mode: it reports every account it would delete or disconnect, "
                "and every subscription it would mark expired, with reasons and the "
                "deciding timestamps, and touches nothing."
            ),
        )
        parser.add_argument(
            '--router-id',
            type=int,
            default=None,
            help=(
                "Sweep only this router id. Defaults to every is_active=True, "
                "manages_hotspot_users=True router."
            ),
        )
        parser.add_argument(
            '--username',
            type=str,
            default=None,
            help=(
                "Restrict the account pass to this single hotspot username (still "
                "requires --router-id). Every other account on the router - including "
                "the lapsed-subscription DB pass, which is account-independent - is "
                "left untouched. Useful for verifying the sweep against one account "
                "without risking any other account on a shared router."
            ),
        )

    def handle(self, *args, **options):
        dry_run = not options['live']
        routers = self._resolve_routers(options['router_id'])
        username_filter = options['username']
        if username_filter and options['router_id'] is None:
            raise CommandError("--username requires --router-id")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "DRY RUN - no router writes, no database writes. Pass --live to apply."
            ))

        for router in routers:
            try:
                self._sweep_router(router, dry_run, username_filter)
            except CommandError:
                raise
            except Exception as e:
                # One router's failure must never stop the rest of the fleet, and must
                # never leave that router half-processed for the next scheduled run to
                # trip over - log and move on, same as sample_router_stats.
                self.stderr.write(self.style.ERROR(
                    f"Unexpected error sweeping router {router.id} ({router.name}): {e}"
                ))
                logger.exception("expire_hotspot_accounts: unexpected error sweeping router %s", router.id)

    def _resolve_routers(self, router_id):
        routers = Router.objects.filter(is_active=True, manages_hotspot_users=True)
        if router_id is not None:
            routers = routers.filter(pk=router_id)
            if not routers.exists():
                raise CommandError(
                    f"No active, manages_hotspot_users=True router found with id={router_id}"
                )
        return list(routers)

    def _sweep_router(self, router, dry_run, username_filter=None):
        # Safety gate first, always - before any connection is even opened. The
        # --router-id/is_active/manages_hotspot_users filter above already excludes
        # unmanaged routers, but this is the same explicit, defense-in-depth check
        # every other router-write path in this codebase makes at the point of use
        # (network_management.utils.router_guard) - nothing here may ever reach a
        # router SurfZone hasn't been enabled to manage.
        try:
            ensure_router_manages_hotspot_users(router, "sweep expired hotspot accounts")
        except RouterNotManagedError as e:
            self.stderr.write(self.style.ERROR(str(e)))
            return

        if router.type != "mikrotik":
            self.stdout.write(self.style.WARNING(
                f"Skipping router {router.id} ({router.name}): sweep only implemented "
                f"for mikrotik, not '{router.type}'"
            ))
            return

        now = timezone.now()

        # Pure DB pass, independent of router reachability and of which account a
        # subscription maps to - must run before the account pass below so an account
        # whose last outstanding subscription lapses on this very run is correctly
        # seen there as "every window passed".
        self._mark_lapsed_subscriptions(router, now, dry_run, username_filter)

        try:
            api_pool = RouterOsApiPool(
                router.ip,
                username=router.username,
                password=router.password,
                port=router.port,
                plaintext_login=True,
            )
            api = api_pool.get_api()
        except Exception as e:
            # Unreachable: log and stop for this router, no partial state - whatever
            # accounts would have been processed just weren't reached, and the next
            # scheduled run picks them up exactly as if this run never happened.
            self.stderr.write(self.style.ERROR(
                f"Router {router.id} ({router.ip}) unreachable, skipping this run: {e}"
            ))
            return

        try:
            users = api.get_resource('/ip/hotspot/user').get() or []
            active_sessions = api.get_resource('/ip/hotspot/active').get() or []
            active_by_user = {}
            for session in active_sessions:
                active_by_user.setdefault(session.get('user'), []).append(session)

            for entry in users:
                if username_filter and entry.get('name') != username_filter:
                    continue
                try:
                    self._sweep_account(router, api, entry, active_by_user, now, dry_run)
                except Exception as e:
                    self.stderr.write(self.style.ERROR(
                        f"Router {router.id}: error processing account "
                        f"'{entry.get('name')}' (id={entry.get('id')}): {e}"
                    ))
                    logger.exception(
                        "expire_hotspot_accounts: error processing account %s on router %s",
                        entry.get('name'), router.id,
                    )
        finally:
            try:
                api_pool.disconnect()
            except Exception:
                pass

    def _mark_lapsed_subscriptions(self, router, now, dry_run, username_filter=None):
        """
        'active' subscriptions whose own end_date has passed, scoped to this router.
        Independent of the account-grouping pass below: a subscription's own status
        reflects whether IT still represents live time, regardless of whether the
        shared router account it maps to gets deleted this run (it might not, if a
        different subscription mapped to the same account still has an open window).
        """
        lapsed = Subscription.objects.filter(
            router_id=router.id, status='active', end_date__isnull=False, end_date__lt=now,
        )
        if username_filter:
            lapsed = lapsed.filter(hotspot_username=username_filter)
        for sub in lapsed:
            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] would mark subscription {sub.id} "
                    f"(username={sub.hotspot_username}) expired: "
                    f"end_date={sub.end_date.isoformat()} < now={now.isoformat()}"
                )
            else:
                sub.status = 'expired'
                sub.save(update_fields=['status', 'updated_at'])
                self.stdout.write(
                    f"Marked subscription {sub.id} (username={sub.hotspot_username}) expired "
                    f"(end_date={sub.end_date.isoformat()})"
                )

    def _sweep_account(self, router, api, entry, active_by_user, now, dry_run):
        username = entry.get('name')
        if not username:
            return

        mapped_subs = list(Subscription.objects.filter(router_id=router.id, hotspot_username=username))
        if not mapped_subs:
            # Not one of ours (RouterOS's own default-trial row, or a manually-created
            # account with no matching Subscription) - never touched by this sweep.
            return

        pending = [s for s in mapped_subs if s.status == 'pending_activation']
        if pending:
            ids = ", ".join(str(s.id) for s in pending)
            self.stdout.write(
                f"Router {router.id}: account '{username}' left alone - subscription(s) "
                f"{ids} are pending_activation (paid, not yet provisioned; the "
                f"reconcile_payments safety-net retry owes them service)."
            )
            return

        online_sessions = active_by_user.get(username, [])
        all_windows_passed = all(
            s.end_date is not None and s.end_date < now for s in mapped_subs
        )

        if all_windows_passed:
            reason = "; ".join(
                f"sub={s.id} status={s.status} "
                f"end_date={s.end_date.isoformat() if s.end_date else None}"
                for s in mapped_subs
            )
            if dry_run:
                if online_sessions:
                    self.stdout.write(
                        f"[DRY RUN] would kick '{username}' "
                        f"({len(online_sessions)} active session(s)) before deleting"
                    )
                self.stdout.write(
                    f"[DRY RUN] would delete /ip/hotspot/user '{username}' "
                    f"(id={entry.get('id')}) - every mapped subscription's window has "
                    f"passed as of now={now.isoformat()}. {reason}"
                )
            else:
                self._kick(api, online_sessions)
                api.get_resource('/ip/hotspot/user').remove(id=entry['id'])
                self.stdout.write(
                    f"Deleted hotspot account '{username}' (id={entry.get('id')}) - "
                    f"every mapped subscription's window has passed. {reason}"
                )
            return

        # At least one mapped window is still open - the account stays. Only
        # remaining question: is it out of connected-time allowance, and if so, is it
        # actually disconnected right now (kick it if not - never rely on RouterOS
        # having already dropped it; see the command's own investigation notes on
        # whether limit-uptime alone drops a live session).
        uptime_seconds = _parse_routeros_duration_seconds(entry.get('uptime')) or 0
        limit_seconds = _parse_routeros_duration_seconds(entry.get('limit-uptime'))
        exhausted = limit_seconds is not None and uptime_seconds >= limit_seconds

        if exhausted and online_sessions:
            detail = (
                f"uptime={entry.get('uptime')} >= limit-uptime={entry.get('limit-uptime')}, "
                f"still inside window (entry stays)"
            )
            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] would kick '{username}' ({len(online_sessions)} active "
                    f"session(s)) - allowance exhausted, {detail}"
                )
            else:
                self._kick(api, online_sessions)
                self.stdout.write(f"Disconnected '{username}' - allowance exhausted, {detail}")

    def _kick(self, api, online_sessions):
        active_resource = api.get_resource('/ip/hotspot/active')
        for session in online_sessions:
            active_resource.remove(id=session['id'])
