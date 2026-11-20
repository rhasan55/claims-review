"""Reproducible synthetic denial-work queue. No patient or payer data."""

from pathlib import Path
from datetime import date, timedelta
import json, math, sqlite3
import numpy as np
from threadpoolctl import threadpool_limits
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, log_loss

ROOT = Path(__file__).resolve().parent
FEATURES = [
    "reason",
    "payer",
    "age_days",
    "prior_denials",
    "has_auth",
    "missing_field",
    "allowed_amount",
]
SEED = 55


def generate(n=12000):
    rng = np.random.default_rng(SEED)
    rows = []
    for i in range(n):
        day = date(2025, 1, 1) + timedelta(days=int(rng.integers(0, 485)))
        reason, payer = int(rng.integers(0, 4)), int(rng.integers(0, 3))
        age = int(rng.integers(2, 131))
        prior = int(rng.integers(0, 4))
        auth, missing = int(rng.random() < 0.65), int(rng.random() < 0.35)
        amount = round(float(rng.lognormal(5.4, 0.8)), 2)
        # Scenario assumptions, not estimates learned from healthcare organizations.
        z = (
            0.9
            - 0.5 * reason
            - 0.3 * payer
            - 0.014 * age
            - 0.35 * prior
            + 0.65 * auth
            - 0.6 * missing
        )
        z += 0.8 * (reason == 0 and missing == 1) - 0.7 * (reason == 2 and auth == 0)
        outcome = int(rng.random() < 1 / (1 + math.exp(-z)))
        rows.append(
            dict(
                episode_id=f"E{i:05}",
                decision_at=day.isoformat(),
                reason=reason,
                payer=payer,
                age_days=age,
                prior_denials=prior,
                has_auth=auth,
                missing_field=missing,
                allowed_amount=amount,
                recovered_within_60d=outcome,
                outcome_known_at=(day + timedelta(days=60)).isoformat(),
                actual_recovered=round(amount * outcome, 2),
            )
        )
    return rows


def metrics(y, p):
    bins = []
    for lo in np.arange(0, 1, 0.1):
        sel = (p >= lo) & (p < lo + 0.1 if lo < 0.9 else p <= 1)
        if sel.any():
            bins.append(
                dict(
                    lower=round(float(lo), 1),
                    n=int(sel.sum()),
                    predicted=float(p[sel].mean()),
                    observed=float(y[sel].mean()),
                )
            )
    ece = sum(b["n"] * abs(b["predicted"] - b["observed"]) for b in bins) / len(y)
    return dict(
        n=len(y),
        auc=float(roc_auc_score(y, p)),
        brier=float(brier_score_loss(y, p)),
        log_loss=float(log_loss(y, p)),
        ece=ece,
        bins=bins,
    )


def fit():
    threadpool_limits(limits=1)
    rows = generate()
    X = np.array([[r[k] for k in FEATURES] for r in rows])
    y = np.array([r["recovered_within_60d"] for r in rows])
    # Training labels must be mature when calibration starts. Calibration labels mature before test starts.
    tr = np.array([r["outcome_known_at"] < "2025-11-01" for r in rows])
    ca = np.array(["2025-11-01" <= r["decision_at"] < "2026-01-01" for r in rows])
    te = np.array(
        [
            r["decision_at"] >= "2026-03-02" and r["outcome_known_at"] <= "2026-08-01"
            for r in rows
        ]
    )
    model = HistGradientBoostingClassifier(
        max_iter=110, max_leaf_nodes=12, l2_regularization=8, random_state=SEED
    ).fit(X[tr], y[tr])
    raw_ca = np.clip(model.predict_proba(X[ca])[:, 1], 1e-6, 1 - 1e-6)
    cal = LogisticRegression(C=1e6, random_state=SEED).fit(
        np.log(raw_ca / (1 - raw_ca)).reshape(-1, 1), y[ca]
    )
    raw = np.clip(model.predict_proba(X[te])[:, 1], 1e-6, 1 - 1e-6)
    prob = cal.predict_proba(np.log(raw / (1 - raw)).reshape(-1, 1))[:, 1]
    test = [r.copy() for r, s in zip(rows, te) if s]
    for r, p in zip(test, prob):
        r["probability"] = float(p)
        r["expected_net"] = round(r["allowed_amount"] * float(p) - 20, 2)
    capacity = 100

    def summary(key):
        selected = sorted(test, key=lambda r: (-key(r), r["episode_id"]))[:capacity]
        return dict(
            claims=len(selected),
            realized_recovered=round(sum(r["actual_recovered"] for r in selected), 2),
            review_cost=20 * len(selected),
            net=round(sum(r["actual_recovered"] - 20 for r in selected), 2),
            expected_net=round(sum(r["expected_net"] for r in selected), 2),
            recovered_claims=sum(r["recovered_within_60d"] for r in selected),
        )

    out = dict(
        seed=SEED,
        synthetic=True,
        features=FEATURES,
        split=dict(
            train=int(tr.sum()),
            calibration=int(ca.sum()),
            test=int(te.sum()),
            train_latest_label=max(
                r["outcome_known_at"] for r, s in zip(rows, tr) if s
            ),
            calibration_latest_label=max(
                r["outcome_known_at"] for r, s in zip(rows, ca) if s
            ),
            test_first_decision=min(r["decision_at"] for r in test),
        ),
        raw=metrics(y[te], raw),
        calibrated=metrics(y[te], prob),
        queue=dict(
            capacity=capacity,
            cost=20,
            oldest=summary(lambda r: r["age_days"]),
            largest=summary(lambda r: r["allowed_amount"]),
            expected_net=summary(lambda r: r["expected_net"]),
        ),
        claims=sorted(test, key=lambda r: r["expected_net"], reverse=True),
    )
    (ROOT / "results.json").write_text(json.dumps(out, indent=2))
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE claim_snapshot (episode_id TEXT PRIMARY KEY,decision_at TEXT,reason INTEGER,payer INTEGER,age_days INTEGER,prior_denials INTEGER,has_auth INTEGER,missing_field INTEGER,allowed_amount REAL,recovered_within_60d INTEGER,outcome_known_at TEXT,actual_recovered REAL)"
    )
    conn.executemany(
        "INSERT INTO claim_snapshot VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [tuple(r.values()) for r in rows],
    )
    # Test the local snapshot SQL; production adaptation in warehouse.sql.
    assert conn.execute("SELECT COUNT(*) FROM claim_snapshot").fetchone()[0] == len(
        rows
    )
    print(
        json.dumps(
            {k: v for k, v in out.items() if k not in ("claims", "raw", "calibrated")},
            indent=2,
        )
    )
    print("Brier raw/calibrated:", out["raw"]["brier"], out["calibrated"]["brier"])
    return out


if __name__ == "__main__":
    fit()
