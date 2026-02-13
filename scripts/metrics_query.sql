-- Metrics query: activation, trust, and tracker KPIs from analytics_events
-- Run in Supabase SQL Editor (or any Postgres client) after events are being captured.
-- Requires table analytics_events and view analytics_daily_events (created by backend init_schema).

-- Daily rollup (all event types)
SELECT day, event_name, events, users
FROM analytics_daily_events
WHERE day >= date_trunc('day', NOW() - INTERVAL '30 days')
ORDER BY day DESC, events DESC
LIMIT 100;

-- Activation: first_apply_pack_created (Phase 0 metric: % users who generate first pack within 10 min)
SELECT date_trunc('day', occurred_at) AS day,
       COUNT(*) AS first_pack_events,
       COUNT(DISTINCT distinct_id) AS unique_users
FROM analytics_events
WHERE event_name = 'first_apply_pack_created'
  AND occurred_at >= NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1 DESC;

-- Trust: trust_report_generated (Phase 0: % parsed jobs with Trust Report viewed)
SELECT date_trunc('day', occurred_at) AS day,
       COUNT(*) AS trust_report_events
FROM analytics_events
WHERE event_name = 'trust_report_generated'
  AND occurred_at >= NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1 DESC;

-- Tracker: application_tracked (Phase 0: % packs that become a tracked application)
SELECT date_trunc('day', occurred_at) AS day,
       COUNT(*) AS tracked_events
FROM analytics_events
WHERE event_name = 'application_tracked'
  AND occurred_at >= NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1 DESC;
