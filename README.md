# Which claim gets worked next?

[Open the interactive report](https://rhasan55.github.io/claims-review/) | [Python analysis](analysis.py) | [SQL Server feature sketch](warehouse.sql)

An independent portfolio demonstration by Raja Hasan, built around Red Sky Health's public Senior Data Scientist posting. It asks two questions: how should a limited billing team prioritize denied claims, and when is a proposed correction supported well enough to review?

**All claims, outcomes and policy passages are synthetic.** This is not Red Sky Health's product, data, model, payer guidance or measured performance. There is no clinical recommendation, live claim submission or external model call.

## Run

Python 3.12:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
OMP_NUM_THREADS=1 python analysis.py
python evidence.py
python -m unittest -v test_analysis.py
python build_report.py
python -m http.server 8768
```

Open `http://localhost:8768`. The generated report also works as a standalone HTML file. Results are fixed by seed 55. Rerun the Python analysis to change the data, not the displayed controls.

## What is implemented

- A gradient-boosted tree estimates 60-day recovery probability for a denial episode. A separate calibration period fits a logistic (Platt) map.
- Labels mature before the following phase begins. Claims have unique episode identifiers. Outcome and future payment fields are excluded from features.
- The report compares calibration curves, Brier score and three work-queue policies at the same review capacity.
- A structured-output validator checks payer, plan, service date, policy availability, exact quotation, evidence IDs, allowed actions and proposed changes.
- Thirteen deliberately constructed candidate outputs exercise the validator. These are **fixtures, not sampled LLM outputs**. Passing them is not an LLM accuracy, security or HIPAA certification.
- `warehouse.sql` sketches a point-in-time SQL Server feature join and 60-day payment label. It is documentation for integration, not tested against a real SQL Server warehouse or a full 837/835 parser.

## How to read the result

The target is recovery observed under an assumed existing workflow. It does not estimate the causal effect of working an extra claim. Queue comparisons reuse a fully observed synthetic outcome for every claim. In real operations, unworked claims have selectively missing outcomes. A prospective randomized or otherwise defensible rollout is needed before claiming revenue lift.

Ranking uses probability times allowed amount minus a fixed $20 review cost. Allowed amount is known at decision time in this constructed dataset. That assumption must be checked locally. Partial payments, reversals, timely-filing limits, action-specific recoverability and time-to-cash need explicit treatment before deployment.

Reason and payer numbers are fictional categories, not CARC/RARC or CPT mappings. Policy retrieval is exact scoped filtering over three fixture documents, not semantic search. The demo implements the contract around an LLM response, not a trained denial-reasoning model. See `llm-contract.md` for the adapter boundary and the next evaluation step.

## First sprint proposal

Start with one denial family and one payer. Reconstruct the claim state available at the original decision, audit payment allocation, create a blinded biller-reviewed test set, and run the model in shadow mode. Measure supported-action rate, abstention, review time, follow-rate, and net recovered revenue on matured cohorts. Investigate errors before expanding automation.

[Sources](sources.md) | [Model and evidence code](analysis.py) | [Evidence contract](evidence.py)
