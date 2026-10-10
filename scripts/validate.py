"""Sanity-check a finished crawl before it is committed. Exits non-zero (and prints why) on a bad run."""
import json
import sys
from pathlib import Path

out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
fac = json.loads((out / "faculty.json").read_text(encoding="utf-8"))
cov = json.loads((out / "coverage.json").read_text(encoding="utf-8"))
f = fac["faculty"]
problems = []
if fac["metadata"]["total"] != len(f):
    problems.append("metadata total does not match record count")
if len(f) < 3000:
    problems.append(f"only {len(f)} faculty records (expected at least 3000)")
sites = [d for d in cov["departments"] if d["site"]]
if len(sites) < 60:
    problems.append(f"only {len(sites)} departments with a website")
ok = [d for d in cov["departments"] if d["status"] == "ok"]
if len(ok) < 25:
    problems.append(f"only {len(ok)} departments produced a faculty list")
enriched = sum(bool(r["research_areas"] or r["email"]) for r in f if r["profile_url"])
if enriched < 300:
    problems.append(f"only {enriched} profiles had email or research details")
ids = [r["id"] for r in f]
if len(set(ids)) != len(ids):
    problems.append("duplicate faculty ids")
print(f"faculty={len(f)} departments_ok={len(ok)}/{len(cov['departments'])} enriched_profiles={enriched}")
if problems:
    print("VALIDATION FAILED:\n - " + "\n - ".join(problems))
    sys.exit(1)
print("Validation passed")
