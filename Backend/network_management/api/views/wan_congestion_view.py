"""
Read-only WAN congestion endpoint - buckets WanSample rows (Stage 1/2 of the
WAN congestion monitor) into 10-minute windows for charting. Reads only the
WanSample table; makes no contact with the router itself.
"""

from datetime import timedelta, timezone as dt_timezone

from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from network_management.models.router_management_model import Router
from network_management.models.wan_sample_model import WanSample

# Mirrors sample_wan's --router-id default resolution (id=6 "surfzone
# nyakweri", the active Starlink WAN router) so the endpoint and the sampler
# agree on which router "the WAN" means without a query param.
DEFAULT_ROUTER_ID = 6
DEFAULT_INTERFACE = 'ether1'
DEFAULT_HOURS = 24
BUCKET_MINUTES = 10


def resolve_wan_router(router_id=None):
    """
    Resolve which Router row to use, mirroring sample_wan's _resolve_router logic.

    Returns (router, error_message) - exactly one of the two is None.
    """
    if router_id is not None:
        router = Router.objects.filter(pk=router_id).first()
        if router is None:
            return None, f"No router found with id={router_id}"
        return router, None

    default_router = Router.objects.filter(pk=DEFAULT_ROUTER_ID, is_active=True).first()
    if default_router:
        return default_router, None

    active_routers = list(Router.objects.filter(is_active=True))
    if len(active_routers) == 1:
        return active_routers[0], None
    if not active_routers:
        return None, (
            "No active router found and default router "
            f"id={DEFAULT_ROUTER_ID} is not active. Specify router_id explicitly."
        )
    ids = ', '.join(str(r.id) for r in active_routers)
    return None, (
        f"Multiple active routers found (ids: {ids}) and default router "
        f"id={DEFAULT_ROUTER_ID} is not active/available. Specify router_id explicitly."
    )


def floor_to_bucket(dt, bucket_minutes=BUCKET_MINUTES):
    """Floor a timezone-aware datetime to the bucket_minutes mark, in UTC."""
    dt = dt.astimezone(dt_timezone.utc)
    floored_minute = (dt.minute // bucket_minutes) * bucket_minutes
    return dt.replace(minute=floored_minute, second=0, microsecond=0)


def bucket_wan_samples(router_id, interface, hours, bucket_minutes=BUCKET_MINUTES):
    """
    Pull WanSample rows for router_id+interface over the last `hours` hours
    and bucket them into bucket_minutes-wide windows, floored to the bucket
    mark (avoids relying on MySQL date-trunc / server timezone behaviour).

    Null-throughput rows (e.g. the very first sample for a router+interface,
    or a counter-reset) are skipped when computing down/up stats but still
    counted in `samples`. Same for null latency/loss (e.g. a row written
    while the router was briefly unreachable). If a bucket has zero valid
    readings for a given metric, that metric is null in the response -
    down_peak_mbps, down_avg_mbps, up_peak_mbps, up_avg_mbps, latency_avg_ms,
    latency_max_ms, and loss_max_pct are all float|null; samples and
    had_unreachable are always present.

    Returns a dict matching the WAN congestion endpoint's response shape.
    """
    since = timezone.now() - timedelta(hours=hours)

    samples = (
        WanSample.objects
        .filter(router_id=router_id, interface=interface, timestamp__gte=since)
        .order_by('timestamp')
    )

    buckets = {}
    order = []
    for sample in samples:
        bucket_start = floor_to_bucket(sample.timestamp, bucket_minutes)
        if bucket_start not in buckets:
            buckets[bucket_start] = {
                'down_values': [],
                'up_values': [],
                'latency_values': [],
                'loss_values': [],
                'samples': 0,
                'had_unreachable': False,
            }
            order.append(bucket_start)
        bucket = buckets[bucket_start]
        bucket['samples'] += 1
        if not sample.reachable:
            bucket['had_unreachable'] = True
        if sample.down_mbps is not None:
            bucket['down_values'].append(sample.down_mbps)
        if sample.up_mbps is not None:
            bucket['up_values'].append(sample.up_mbps)
        if sample.latency_ms is not None:
            bucket['latency_values'].append(sample.latency_ms)
        if sample.packet_loss_pct is not None:
            bucket['loss_values'].append(sample.packet_loss_pct)

    result_buckets = []
    for bucket_start in order:
        b = buckets[bucket_start]
        result_buckets.append({
            'bucket_start': bucket_start.isoformat(),
            'down_peak_mbps': round(max(b['down_values']), 2) if b['down_values'] else None,
            'down_avg_mbps': round(sum(b['down_values']) / len(b['down_values']), 2) if b['down_values'] else None,
            'up_peak_mbps': round(max(b['up_values']), 2) if b['up_values'] else None,
            'up_avg_mbps': round(sum(b['up_values']) / len(b['up_values']), 2) if b['up_values'] else None,
            'latency_avg_ms': round(sum(b['latency_values']) / len(b['latency_values']), 2) if b['latency_values'] else None,
            'latency_max_ms': round(max(b['latency_values']), 2) if b['latency_values'] else None,
            'loss_max_pct': round(max(b['loss_values']), 2) if b['loss_values'] else None,
            'samples': b['samples'],
            'had_unreachable': b['had_unreachable'],
        })

    return {
        'router_id': router_id,
        'interface': interface,
        'window_hours': hours,
        'buckets': result_buckets,
    }


class WanCongestionView(APIView):
    """
    GET /wan-congestion/?hours=24&router_id=6&interface=ether1

    Read-only, admin-only. Buckets WanSample rows into 10-minute windows.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            hours = int(request.query_params.get('hours', DEFAULT_HOURS))
        except (TypeError, ValueError):
            return Response({'error': 'hours must be an integer'}, status=400)
        if hours <= 0:
            return Response({'error': 'hours must be positive'}, status=400)

        router_id_param = request.query_params.get('router_id')
        router_id = None
        if router_id_param is not None:
            try:
                router_id = int(router_id_param)
            except ValueError:
                return Response({'error': 'router_id must be an integer'}, status=400)

        interface = request.query_params.get('interface', DEFAULT_INTERFACE)

        router, error = resolve_wan_router(router_id)
        if error:
            status_code = 404 if router_id is not None else 400
            return Response({'error': error}, status=status_code)

        result = bucket_wan_samples(router.id, interface, hours)
        return Response(result)
