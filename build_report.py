from pathlib import Path
import json

P = Path(__file__).parent
r = json.loads((P / "results.json").read_text())
e = json.loads((P / "evidence-results.json").read_text())
t = (
    (P / "report-template.html")
    .read_text()
    .replace("__RESULTS__", json.dumps(r))
    .replace("__EVIDENCE__", json.dumps(e))
)
(P / "index.html").write_text(t)
print("Standalone report written. Synthetic observations:", len(r["claims"]))
