from django.db import models

from network_management.models.router_management_model import Router


class WanSample(models.Model):
    """
    Periodic sample of a WAN uplink's throughput, latency, and reachability.

    Distinct from BandwidthUsageHistory, which tracks per-subscriber usage:
    this table tracks the health of the router's upstream (e.g. Starlink)
    connection itself, independent of any client allocation.
    """

    router = models.ForeignKey(
        Router,
        on_delete=models.PROTECT,
        related_name='wan_samples',
        help_text="Router this WAN sample was taken from"
    )
    interface = models.CharField(max_length=50, help_text="WAN interface name (e.g. 'ether1')")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    rx_bytes = models.BigIntegerField(
        null=True, blank=True,
        help_text="Cumulative rx-byte counter at sample time (null if the router was unreachable)"
    )
    tx_bytes = models.BigIntegerField(
        null=True, blank=True,
        help_text="Cumulative tx-byte counter at sample time (null if the router was unreachable)"
    )

    interval_seconds = models.FloatField(
        null=True, blank=True,
        help_text="Seconds since the previous sample for this router+interface"
    )
    down_mbps = models.FloatField(
        null=True, blank=True,
        help_text="Average download throughput over the interval, derived from the rx_bytes delta"
    )
    up_mbps = models.FloatField(
        null=True, blank=True,
        help_text="Average upload throughput over the interval, derived from the tx_bytes delta"
    )

    latency_ms = models.FloatField(null=True, blank=True, help_text="Average ping RTT in milliseconds")
    packet_loss_pct = models.FloatField(null=True, blank=True, help_text="Ping packet loss percentage")
    reachable = models.BooleanField(default=True, help_text="Whether the router responded to this sampling attempt")

    class Meta:
        indexes = [
            models.Index(fields=['router', 'interface', 'timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.router.name} {self.interface} @ {self.timestamp}"
