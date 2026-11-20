-- Executable SQLite counterpart to the SQL Server integration sketch.
-- Inputs are normalized synthetic events, not raw 837/835 messages.
-- :as_of is supplied by the caller. Payments are already deduplicated by event ID.
WITH snapshots AS (
 SELECT e.episode_id,e.claim_id,e.decision_at,v.recorded_at,
        v.version_id,v.payer,v.allowed_cents,v.reason,
        ROW_NUMBER() OVER (
          PARTITION BY e.episode_id ORDER BY v.recorded_at DESC,v.version_id DESC
        ) AS version_rank
 FROM episodes e JOIN claim_versions v USING(claim_id)
 WHERE v.recorded_at <= e.decision_at AND e.decision_at <= :as_of
), outcomes AS (
 SELECT e.episode_id,
   COALESCE(SUM(CASE WHEN p.posted_at > e.decision_at
                          AND p.posted_at <= date(e.decision_at,'+60 days')
                          AND p.known_at <= :as_of
                     THEN p.net_paid_cents ELSE 0 END),0) AS recovered_cents
 FROM episodes e LEFT JOIN payments p USING(claim_id)
 WHERE date(e.decision_at,'+60 days') <= :as_of
 GROUP BY e.episode_id
)
SELECT s.episode_id,s.claim_id,s.decision_at,s.version_id,s.recorded_at,
       s.payer,s.allowed_cents,s.reason,o.recovered_cents,
       CASE WHEN o.recovered_cents > 0 THEN 1 ELSE 0 END AS recovered_60d
FROM snapshots s JOIN outcomes o USING(episode_id)
WHERE s.version_rank=1 ORDER BY s.episode_id;
