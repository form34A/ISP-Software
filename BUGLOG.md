# Bug Log

## Open

### Client Growth chart shows fabricated numbers on empty data
- **Reported by:** Roger, 2026-07-02, after DB wipe to clean baseline (0 real clients).
- **Symptom:** The "Client Growth" chart on the Subscribers/Analytics view (`Frontend/Dashboard/src/Pages/UserManagement/Subscribers.jsx:1925`, `AnalyticsChart` component) shows non-zero stats (e.g. "Avg 20.1") with zero real clients in the database. Misleading for a real ISP owner reviewing the dashboard.
- **Investigated:** The active `AnalyticsChart.jsx` (`Frontend/Dashboard/src/components/ClientManagement/AnalyticsChart.jsx:507-515`) already renders a correct "No Data Available" empty state when `chartData.labels.length === 0` — a fake-sample-data fallback only exists in a dead, commented-out earlier version of the same file (lines 1-267) and is not executed. `useAnalytics.js` (the hook feeding `analyticsDashboard.charts.clients`) has no mock-data generation either.
- **Likely root cause:** The backend analytics endpoint(s) that populate `charts.clients` (`Backend/user_management/api/views/analytics_views.py`, same file already tracked for the empty-DB crash bugs — F-expression comparison bug near line 744, ~15 unguarded divisions, "Negative indexing is not supported" error seen in logs during subscription-data generation) is likely computing/interpolating a non-empty trend even when there's no underlying data, rather than returning an empty `{labels: [], datasets: []}` structure. Needs backend-side tracing to confirm, but the frontend chart component itself is not the source.
- **Fix direction:** When fixing analytics_views.py for the empty-DB crashes (existing task: "Guard analytics_views.py against empty DB"), also verify each chart-data method returns a genuinely empty series (not synthesized/interpolated values) when there are 0 underlying records, so the frontend's existing empty-state UI kicks in correctly.
- **Status:** Not fixed. Logged for later, to be addressed alongside the analytics_views.py empty-DB guard work.
