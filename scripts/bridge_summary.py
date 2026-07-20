"""Print a one-line signal-bridge summary for the daily_collect log (forward experiment).

Korean metric labels live here (UTF-8 .py, read by Python) so daily_collect.ps1 stays
ASCII-only (Windows PowerShell 5.1 misreads non-ASCII scripts).

    python scripts/bridge_summary.py [report.json]
"""

from __future__ import annotations

import io
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "modules/signal-bridge/output/report.json"
report = json.load(io.open(path, encoding="utf-8"))
m = {x["label"]: x["value"] for x in report.get("metrics", [])}
joined = m.get("조인(양측 신호)")
led = m.get("소셜 선행")
only = m.get("소셜-온리 관측대상")
cov = m.get("워치리스트 커버리지")
sub = report.get("subtitle", "")
print(f"SUMMARY joined={joined} social-led={led} social-only={only} watch-cov={cov} | {sub}")
