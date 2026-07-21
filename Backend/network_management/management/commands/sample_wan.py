import re

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from routeros_api import RouterOsApiPool

from network_management.models.router_management_model import Router
from network_management.models.wan_sample_model import WanSample

# The router row considered the primary Starlink WAN uplink when --router-id
# is not given (see network-management inspection: id=6 "surfzone nyakweri",
# default route gateway 100.64.0.1 via ether1 is Starlink's CGNAT range).
DEFAULT_ROUTER_ID = 6

DURATION_PATTERN = re.compile(r'(\d+(?:\.\d+)?)(ms|us|ns|d|h|m|s)')
DURATION_UNIT_TO_MS = {
    'd': 86400000.0,
    'h': 3600000.0,
    'm': 60000.0,
    's': 1000.0,
    'ms': 1.0,
    'us': 0.001,
    'ns': 0.000001,
}


class Command(BaseCommand):
    help = (
        "Take one read-only WAN congestion sample (interface counters + ping) "
        "from a MikroTik router and store it as a WanSample row."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--router-id',
            type=int,
            default=None,
            help=(
                f"Router id to sample. Defaults to the active Starlink router "
                f"(id={DEFAULT_ROUTER_ID}), falling back to the single active "
                f"router if that id isn't available."
            )
        )
        parser.add_argument(
            '--interface',
            type=str,
            default='ether1',
            help="WAN interface name to sample (default: ether1)"
        )
        parser.add_argument(
            '--ping-target',
            type=str,
            default='8.8.8.8',
            help="Address the router pings to measure latency/loss (default: 8.8.8.8)"
        )
        parser.add_argument(
            '--ping-count',
            type=int,
            default=10,
            help="Number of ping echoes the router sends (default: 10)"
        )

    def handle(self, *args, **options):
        router = self._resolve_router(options['router_id'])
        interface_name = options['interface']
        ping_target = options['ping_target']
        ping_count = options['ping_count']

        try:
            api_pool = RouterOsApiPool(
                router.ip,
                username=router.username,
                password=router.password,
                port=router.port,
                plaintext_login=True
            )
            api = api_pool.get_api()
        except Exception as e:
            self._write_unreachable_sample(router, interface_name)
            self.stderr.write(self.style.ERROR(
                f"Could not connect to router {router.id} ({router.ip}): {e}"
            ))
            return

        try:
            # Ping first, then read counters and save back-to-back, so a row's
            # saved timestamp sits right next to its counter read with no ping
            # delay in between. This keeps interval_seconds (used for the next
            # sample's throughput calc) equal to true counter-read-to-read time.
            latency_ms, packet_loss_pct = self._sample_ping(api, ping_target, ping_count)

            interfaces = api.get_resource('/interface').get(name=interface_name)
            if not interfaces:
                raise CommandError(
                    f"Interface '{interface_name}' not found on router {router.id} ({router.ip})"
                )
            iface = interfaces[0]
            rx_bytes = int(iface.get('rx-byte', 0))
            tx_bytes = int(iface.get('tx-byte', 0))

            interval_seconds, down_mbps, up_mbps = self._compute_throughput(
                router, interface_name, rx_bytes, tx_bytes
            )

            sample = WanSample.objects.create(
                router=router,
                interface=interface_name,
                rx_bytes=rx_bytes,
                tx_bytes=tx_bytes,
                interval_seconds=interval_seconds,
                down_mbps=down_mbps,
                up_mbps=up_mbps,
                latency_ms=latency_ms,
                packet_loss_pct=packet_loss_pct,
                reachable=True,
            )

            self.stdout.write(self.style.SUCCESS(
                f"WanSample #{sample.id}: {interface_name} rx={rx_bytes} tx={tx_bytes} "
                f"down={down_mbps} up={up_mbps} mbps interval={interval_seconds}s "
                f"latency={latency_ms}ms loss={packet_loss_pct}%"
            ))
        except CommandError:
            raise
        except Exception as e:
            self._write_unreachable_sample(router, interface_name)
            self.stderr.write(self.style.ERROR(
                f"WAN sampling failed for router {router.id} ({router.ip}): {e}"
            ))
        finally:
            try:
                api_pool.disconnect()
            except Exception:
                pass

    def _resolve_router(self, router_id):
        if router_id is not None:
            try:
                return Router.objects.get(pk=router_id)
            except Router.DoesNotExist:
                raise CommandError(f"No router found with id={router_id}")

        default_router = Router.objects.filter(pk=DEFAULT_ROUTER_ID, is_active=True).first()
        if default_router:
            return default_router

        active_routers = list(Router.objects.filter(is_active=True))
        if len(active_routers) == 1:
            return active_routers[0]
        if not active_routers:
            raise CommandError(
                "No active router found and default router "
                f"id={DEFAULT_ROUTER_ID} is not active. Pass --router-id explicitly."
            )
        ids = ', '.join(str(r.id) for r in active_routers)
        raise CommandError(
            f"Multiple active routers found (ids: {ids}) and default router "
            f"id={DEFAULT_ROUTER_ID} is not active/available. Pass --router-id explicitly."
        )

    def _compute_throughput(self, router, interface_name, rx_bytes, tx_bytes):
        prev = (
            WanSample.objects
            .filter(router=router, interface=interface_name, rx_bytes__isnull=False, tx_bytes__isnull=False)
            .order_by('-timestamp')
            .first()
        )
        if prev is None:
            return None, None, None

        interval_seconds = (timezone.now() - prev.timestamp).total_seconds()
        if interval_seconds <= 0:
            return None, None, None

        if rx_bytes < prev.rx_bytes or tx_bytes < prev.tx_bytes:
            # Counter reset (e.g. router reboot) - keep the interval, drop the rates.
            return interval_seconds, None, None

        down_mbps = (rx_bytes - prev.rx_bytes) * 8 / interval_seconds / 1_000_000
        up_mbps = (tx_bytes - prev.tx_bytes) * 8 / interval_seconds / 1_000_000
        return interval_seconds, down_mbps, up_mbps

    def _sample_ping(self, api, ping_target, ping_count):
        """
        Issue a read-only /ping from the router and return (latency_ms, packet_loss_pct).
        Defensive about exact reply/summary field shapes since these haven't been
        confirmed against a live router yet - falls back to computing from the
        individual echo replies if the router doesn't return a usable summary.
        """
        try:
            replies = api.get_resource('/').call(
                'ping', {'address': ping_target, 'count': str(ping_count)}
            )
        except Exception as e:
            self.stderr.write(self.style.WARNING(f"Ping to {ping_target} failed: {e}"))
            return None, None

        done_message = getattr(replies, 'done_message', None) or {}

        packet_loss_pct = self._to_float(done_message.get('packet-loss'))
        latency_ms = self._parse_duration_ms(done_message.get('avg-rtt'))

        if packet_loss_pct is not None and latency_ms is not None:
            return latency_ms, packet_loss_pct

        # Fallback: derive from the individual echo replies.
        sent = len(replies)
        rtts_ms = []
        for reply in replies:
            time_val = reply.get('time')
            if time_val is not None and 'timeout' not in reply:
                parsed = self._parse_duration_ms(time_val)
                if parsed is not None:
                    rtts_ms.append(parsed)

        if packet_loss_pct is None and sent:
            packet_loss_pct = round((sent - len(rtts_ms)) / sent * 100, 2)

        if latency_ms is None and rtts_ms:
            latency_ms = sum(rtts_ms) / len(rtts_ms)

        return latency_ms, packet_loss_pct

    def _write_unreachable_sample(self, router, interface_name):
        """Record a failed sampling attempt - no counters were read, so all metrics are null."""
        WanSample.objects.create(
            router=router,
            interface=interface_name,
            rx_bytes=None,
            tx_bytes=None,
            interval_seconds=None,
            down_mbps=None,
            up_mbps=None,
            latency_ms=None,
            packet_loss_pct=None,
            reachable=False,
        )

    @staticmethod
    def _to_float(value):
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_duration_ms(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return None
        matches = DURATION_PATTERN.findall(text)
        if matches:
            return sum(float(amount) * DURATION_UNIT_TO_MS[unit] for amount, unit in matches)
        try:
            return float(text)
        except ValueError:
            return None
