"""
Shared definition of valid Dashboard-card visibility identifiers.

This is the one place that lists what a user is allowed to hide on the main
Dashboard (GridStats.jsx) - the account app's dashboard-preferences endpoint
validates against it, and the dashboard app can import the same constants
when it comes time to actually filter grid_items/charts by these prefs, so
the two can't silently drift apart.
"""

# dashboard/views.py DashboardView.get() grid_items ids 1-14 (fixed at 14
# entries; update this if that list's id range ever changes).
VALID_GRID_ITEM_IDS = frozenset(range(1, 15))

# The 8 stable keys GridStats.jsx pulls off the /api/dashboard/ payload for
# its chart components (see processedData in GridStats.jsx).
VALID_CHART_KEYS = frozenset({
    "system_load",
    "client_types",
    "sales_data",
    "revenue_data",
    "plan_performance",
    "financial_data",
    "visitor_data",
    "new_subscriptions",
})

# Total size of the valid-identifier universe (14 cards + 8 charts) - a
# submitted "hidden" list can never legitimately need to be longer than this.
MAX_HIDDEN_ITEMS = len(VALID_GRID_ITEM_IDS) + len(VALID_CHART_KEYS)


def is_valid_dashboard_pref_key(key):
    """True if `key` is a recognised 'card:<id>' or 'chart:<key>' identifier."""
    if not isinstance(key, str):
        return False

    if key.startswith("card:"):
        suffix = key[len("card:"):]
        return suffix.isdigit() and int(suffix) in VALID_GRID_ITEM_IDS

    if key.startswith("chart:"):
        suffix = key[len("chart:"):]
        return suffix in VALID_CHART_KEYS

    return False
