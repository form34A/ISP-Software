"""
Shared conversion helpers for turning a raw RouterOS /system/resource reply
into the values RouterStats actually stores.

Used by both the on-demand RouterStatsView (browser-triggered) and the
sample_router_stats management command (scheduled), so the two write paths
can't drift back into disagreeing about what "memory" or "temperature" mean.
"""


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_system_resource(system_info):
    """
    Convert a raw RouterOS /system/resource dict (as returned by
    api.get_resource('/system/resource').get()[0]) into the three values
    RouterStats needs.

    Returns (cpu_percent, memory_percent, temperature):
    - cpu_percent: RouterOS's own 0-100 cpu-load reading.
    - memory_percent: computed as (total-memory - free-memory) / total-memory
      * 100 - a true 0-100 percentage of memory in use, not the raw
      free-memory byte count RouterStatsView used to store.
    - temperature: float(cpu-temperature) if the router reported that key at
      all, else None. Many boards (this fleet's hEX S included) have no
      thermal sensor and simply omit the key - that must stay None, not 0,
      since 0 is a value a board with a working sensor could genuinely report.
    """
    cpu_percent = safe_float(system_info.get('cpu-load', 0))

    total_memory = safe_float(system_info.get('total-memory', 0))
    free_memory = safe_float(system_info.get('free-memory', 0))
    memory_percent = (
        (total_memory - free_memory) / total_memory * 100
        if total_memory > 0 else 0.0
    )

    temperature = (
        safe_float(system_info.get('cpu-temperature'))
        if 'cpu-temperature' in system_info else None
    )

    return cpu_percent, memory_percent, temperature
