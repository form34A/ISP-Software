"""
Shared definition of valid Dashboard-card visibility identifiers and labels.

This is the one place that lists what a user is allowed to hide on the main
Dashboard (GridStats.jsx) - the account app's dashboard-preferences endpoint
validates against it and builds its "available" list from it, and
dashboard/views.py imports GRID_ITEM_LABELS to build grid_items instead of
repeating the label strings, so the two can't silently drift apart.
"""

# dashboard/views.py DashboardView.get() grid_items - the "label" value for
# each of the 14 fixed stat-card ids. dashboard/views.py imports this dict
# directly rather than hardcoding these strings a second time.
GRID_ITEM_LABELS = {
    1: "Current Online Users",
    2: "Active Subscriptions",
    3: "Monthly Revenue",
    4: "Today's Revenue",
    5: "Network Uptime",
    6: "Connection Quality",
    7: "Router Health",
    8: "Active Plans",
    9: "New Subscriptions (Week)",
    10: "System Load",
    11: "Plan Categories",
    12: "Hotspot Revenue",
    13: "PPPoE Revenue",
    14: "Network Capacity",
}

# The 8 stable chart-data keys GridStats.jsx pulls off the /api/dashboard/
# payload, mapped to the exact `chartName` string each one is passed as in
# GridStats.jsx. Python can't import a JS literal, so these are copied from
# the live chartName props there - if either side renames a chart, update
# both. (Everything else in this module *is* a single source of truth;
# this dict is the one place cross-language drift is still possible.)
CHART_LABELS = {
    "system_load": "System Load Monitor",
    "client_types": "Client Type Distribution",
    "sales_data": "Sales Performance",
    "revenue_data": "Revenue Analysis",
    "plan_performance": "Plan Performance",
    "financial_data": "Financial Overview",
    "visitor_data": "Plan Popularity",
    "new_subscriptions": "Subscription Growth",
}

VALID_GRID_ITEM_IDS = frozenset(GRID_ITEM_LABELS.keys())
VALID_CHART_KEYS = frozenset(CHART_LABELS.keys())

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


def get_available_dashboard_items():
    """
    Every toggleable Dashboard item, in a stable order, for the
    dashboard-preferences GET response - e.g.
    {"key": "card:1", "label": "Current Online Users", "group": "Stat Cards"}.
    """
    items = [
        {"key": f"card:{item_id}", "label": label, "group": "Stat Cards"}
        for item_id, label in sorted(GRID_ITEM_LABELS.items())
    ]
    items += [
        {"key": f"chart:{chart_key}", "label": label, "group": "Charts"}
        for chart_key, label in CHART_LABELS.items()
    ]
    return items
