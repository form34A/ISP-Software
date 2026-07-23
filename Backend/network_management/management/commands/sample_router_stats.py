import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from routeros_api import RouterOsApiPool
from routeros_api.exceptions import RouterOsApiConnectionError, RouterOsApiCommunicationError

from network_management.models.router_management_model import Router, RouterStats, RouterConnectionTest
from network_management.utils.router_stats_helpers import safe_float, parse_system_resource


class Command(BaseCommand):
    help = (
        "Take one read-only system-resource sample (cpu/memory/temperature/clients) "
        "from each active MikroTik router and store it as a RouterStats row, plus a "
        "RouterConnectionTest row timing the round trip. Read-only against the router "
        "- no config, no queue, no writes of any kind on the device itself."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--router-id',
            type=int,
            default=None,
            help="Sample only this router id. Defaults to every is_active=True router."
        )

    def handle(self, *args, **options):
        routers = self._resolve_routers(options['router_id'])

        for router in routers:
            try:
                self._sample_router(router)
            except CommandError:
                raise
            except Exception as e:
                # Per-router failures must not stop the rest of the fleet from
                # being sampled - log and move on.
                self.stderr.write(self.style.ERROR(
                    f"Unexpected error sampling router {router.id} ({router.ip}): {e}"
                ))

    def _resolve_routers(self, router_id):
        routers = Router.objects.filter(is_active=True)
        if router_id is not None:
            routers = routers.filter(pk=router_id)
            if not routers.exists():
                raise CommandError(
                    f"No active router found with id={router_id}"
                )
        return list(routers)

    def _sample_router(self, router):
        if router.type != "mikrotik":
            self.stdout.write(self.style.WARNING(
                f"Skipping router {router.id} ({router.name}): "
                f"sampling only implemented for mikrotik, not '{router.type}'"
            ))
            return

        started = time.monotonic()
        try:
            api_pool = RouterOsApiPool(
                router.ip,
                username=router.username,
                password=router.password,
                port=router.port,
                plaintext_login=True
            )
            api = api_pool.get_api()

            system_list = api.get_resource("/system/resource").get()
            system = system_list[0] if system_list else {}

            hotspot = api.get_resource("/ip/hotspot/active").get() or []
            pppoe_active = api.get_resource("/ppp/active").get() or []

            response_time = time.monotonic() - started

            api_pool.disconnect()
        except (RouterOsApiConnectionError, RouterOsApiCommunicationError) as e:
            self._record_failure(router, e)
            return
        except Exception as e:
            self._record_failure(router, e)
            return

        cpu, memory_percent, temperature = parse_system_resource(system)
        uptime = system.get("uptime", "0")

        # throughput is intentionally left at 0 here - sample_wan already reads
        # this router's WAN interface counters on its own schedule, and this
        # command isn't meant to poll /interface a second time for the same data.
        throughput = 0.0

        total_hdd = safe_float(system.get("total-hdd-space", 1))
        free_hdd = safe_float(system.get("free-hdd-space", 0))
        disk_percent = (free_hdd / total_hdd * 100) if total_hdd else 0.0

        stats = RouterStats.objects.create(
            router=router,
            cpu=cpu,
            memory=memory_percent,
            connected_clients_count=len(hotspot) + len(pppoe_active),
            hotspot_clients=len(hotspot),
            pppoe_clients=len(pppoe_active),
            uptime=uptime,
            signal=-60,  # no signal data on a wired mikrotik system-resource read; matches RouterStatsView's existing placeholder
            temperature=temperature,
            throughput=throughput,
            disk=disk_percent,
        )

        RouterConnectionTest.objects.create(
            router=router,
            success=True,
            response_time=response_time,
            system_info=system,
        )

        firmware_version = system.get("version") or router.firmware_version
        router.firmware_version = firmware_version
        router.connection_status = 'connected'
        router.last_seen = timezone.now()
        router.last_connection_test = timezone.now()
        router.save(update_fields=[
            'firmware_version', 'connection_status', 'last_seen', 'last_connection_test'
        ])

        self.stdout.write(self.style.SUCCESS(
            f"RouterStats #{stats.id} for router {router.id} ({router.name}): "
            f"cpu={cpu:.1f}% memory={memory_percent:.1f}% "
            f"temperature={'n/a' if temperature is None else f'{temperature:.1f}C'} "
            f"clients={stats.connected_clients_count} response_time={response_time:.3f}s"
        ))

    def _record_failure(self, router, error):
        RouterConnectionTest.objects.create(
            router=router,
            success=False,
            response_time=None,
            error_messages=[str(error)],
        )
        router.connection_status = 'disconnected'
        router.save(update_fields=['connection_status'])

        self.stderr.write(self.style.ERROR(
            f"Could not sample router {router.id} ({router.ip}): {error}"
        ))
