# Checks and development notes

## Data and evaluation

- 12,000 synthetic denial episodes, one episode per claim.
- 5,956 training, 1,507 calibration and 1,551 test episodes. Gaps allow 60-day outcome labels to mature.
- Last training label: October 31, 2025. Calibration starts November 1, 2025.
- Last calibration label: March 1, 2026. Test starts March 2, 2026.
- Outcome fields and later remittances are excluded from model features.
- Brier score: 0.1582 before calibration, 0.1578 after. The difference is small and is not claimed as statistically significant.

## Reconciliation

The browser and Python queues use the same episode-ID tie breaker. Each table reconciles recovered amounts less $20 per selected claim. Browser checks covered capacities of 25 and 100 and an unsupported identifier example.

## Executable SQL check

`ledger.py` executes `panel.sql` over synthetic claim versions and remittance events. It verifies that future claim edits do not change earlier features, exact payment replays count once, reversals reduce recovery, immature outcomes are omitted, and late or out-of-window payments do not enter an as-of label. Conflicting event replays and ambiguous episode allocation are rejected. This small fixture is separate from the model generator; it does not prove a real warehouse mapping.

## Evidence contract

Thirteen hand-authored fixtures cover supported identifiers, wrong payer or plan, future or expired policy, an unsupported quotation, invented values, missing evidence, unknown fields, unauthorized action and cross-action reuse of a correction schema. Eighteen unit tests cover the data, period boundaries, output contract and queue reconciliation.

These are regression tests, not an independent LLM benchmark. A matching quotation does not validate free-form rationale. Only member-ID corrections have a supported change schema. Other actions require manual review.

## Review changes

An initial UI sort used a different tie order from Python for equally old claims. Both now use episode ID as a deterministic tie breaker. A later review found that another action could reuse the member-ID correction rule; the validator now holds that action rather than treating it as supported.

## Remaining work before operational use

Audit the actual 837/835 mappings and reversals, allocate partial payments correctly, incorporate payer-specific deadlines and costs, build a biller-adjudicated retrieval/action set, test unseen policies, and measure intervention effects prospectively. This repository implements none of the real organization's access controls or production integrations.
