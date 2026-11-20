-- SQL Server sketch. Assumed normalized tables, not an EDI parser.
-- Grain: one denial episode at the first decision time. No raw PHI selected.
-- @AsOf is a warehouse timestamp supplied by the caller.
WITH Episodes AS (
 SELECT EpisodeId, ClaimId, MIN(DeniedAt) AS DecisionAt
 FROM DenialEvents WHERE DeniedAt <= @AsOf
 GROUP BY EpisodeId, ClaimId
), Versions AS (
 SELECT e.EpisodeId,e.DecisionAt,c.ClaimId,c.PayerId,c.PlanId,
        c.ServiceDate,c.AllowedAmount,c.ReasonCategory,c.AuthorizationPresent,
        ROW_NUMBER() OVER(PARTITION BY e.EpisodeId ORDER BY c.RecordedAt DESC,c.VersionId DESC) AS rn
 FROM Episodes e JOIN ClaimVersions c ON c.ClaimId=e.ClaimId
 WHERE c.RecordedAt<=e.DecisionAt
), MatureOutcomes AS (
 SELECT e.EpisodeId,
   SUM(CASE WHEN r.PostedAt>e.DecisionAt AND r.PostedAt<=DATEADD(day,60,e.DecisionAt)
            THEN r.PaidAmount-r.ReversalAmount ELSE 0 END) AS NetRecovered60d
 FROM Episodes e LEFT JOIN RemittanceEvents r ON r.ClaimId=e.ClaimId
 -- RemittanceEvents must have an immutable unique payment-event key to avoid replayed 835 double counts.
 WHERE DATEADD(day,60,e.DecisionAt)<=@AsOf
 GROUP BY e.EpisodeId
)
SELECT v.*,CASE WHEN o.NetRecovered60d>0 THEN 1 ELSE 0 END AS Recovered60d,
       o.NetRecovered60d
FROM Versions v JOIN MatureOutcomes o ON o.EpisodeId=v.EpisodeId
WHERE v.rn=1;
-- Label columns and post-decision remittances MUST NOT enter model features.
-- Multiple episodes per claim require an allocation rule for shared payments.
-- This example assumes one episode per claim; reject ambiguous matches in production.
