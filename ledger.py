"""A small, executable point-in-time event check, independent of model simulation.

Normalized synthetic claim versions and remittance events only. No EDI parsing.
One episode per claim is enforced so payment allocation is unambiguous.
"""

from pathlib import Path
import json
import sqlite3

ROOT = Path(__file__).resolve().parent


def deduplicate(events):
    unique = {}
    for event in events:
        key = event["event_id"]
        if key in unique and unique[key] != event:
            raise ValueError(f"Conflicting remittance event: {key}")
        if event["known_at"] < event["posted_at"]:
            raise ValueError("Payment cannot be known before it is posted")
        unique[key] = event
    return list(unique.values())


def fixture():
    episodes = [
        ("E01", "C01", "2026-01-10"),
        ("E02", "C02", "2026-01-10"),
        ("E03", "C03", "2026-07-20"),  # immature at August 1
        ("E04", "C04", "2026-01-10"),  # payment outside the 60-day window
        ("E05", "C05", "2026-01-10"),  # payment received late by warehouse
    ]
    versions = [
        ("C01", 1, "2026-01-09", "A", 10000, "missing_identifier"),
        ("C01", 2, "2026-02-01", "A", 90000, "corrected_later"),
        ("C02", 1, "2026-01-09", "B", 20000, "authorization"),
        ("C03", 1, "2026-07-19", "A", 10000, "missing_identifier"),
        ("C04", 1, "2026-01-09", "B", 10000, "other"),
        ("C05", 1, "2026-01-09", "A", 10000, "other"),
    ]

    def event(event_id, claim, posted, known, amount):
        return dict(
            event_id=event_id,
            claim_id=claim,
            posted_at=posted,
            known_at=known,
            net_paid_cents=amount,
        )

    payment = event("P01", "C01", "2026-01-20", "2026-01-20", 8000)
    events = [
        payment,
        payment.copy(),
        event("R01", "C01", "2026-02-01", "2026-02-01", -3000),
        event("P02", "C02", "2026-01-25", "2026-01-25", 15000),
        event("R02", "C02", "2026-02-05", "2026-02-05", -15000),
        event("P04", "C04", "2026-04-01", "2026-04-01", 10000),
        event("P05", "C05", "2026-01-20", "2026-08-10", 10000),
    ]
    return episodes, versions, events


def build(episodes, versions, events, as_of="2026-08-01"):
    claims = [e[1] for e in episodes]
    if len(set(claims)) != len(claims):
        raise ValueError(
            "Multiple episodes require an explicit payment-allocation rule"
        )
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE episodes(episode_id TEXT PRIMARY KEY,claim_id TEXT UNIQUE,decision_at TEXT);
    CREATE TABLE claim_versions(claim_id TEXT,version_id INTEGER,recorded_at TEXT,payer TEXT,
        allowed_cents INTEGER,reason TEXT,PRIMARY KEY(claim_id,version_id));
    CREATE TABLE payments(event_id TEXT PRIMARY KEY,claim_id TEXT,posted_at TEXT,known_at TEXT,net_paid_cents INTEGER);
    """)
    conn.executemany("INSERT INTO episodes VALUES(?,?,?)", episodes)
    conn.executemany("INSERT INTO claim_versions VALUES(?,?,?,?,?,?)", versions)
    conn.executemany(
        "INSERT INTO payments VALUES(?,?,?,?,?)",
        [
            tuple(
                e[k]
                for k in (
                    "event_id",
                    "claim_id",
                    "posted_at",
                    "known_at",
                    "net_paid_cents",
                )
            )
            for e in deduplicate(events)
        ],
    )
    result = [
        dict(r)
        for r in conn.execute((ROOT / "panel.sql").read_text(), {"as_of": as_of})
    ]
    conn.close()
    return result


if __name__ == "__main__":
    result = build(*fixture())
    (ROOT / "ledger-results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
