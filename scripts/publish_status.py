"""Publish the final (or failed) run state to the status branch. Used by the workflow's always() step."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from atlas.publish import push_status, read_json  # noqa: E402

out = Path(os.getenv("ATLAS_OUT", "docs/data"))
state = sys.argv[1] if len(sys.argv) > 1 else "failed"
message = sys.argv[2] if len(sys.argv) > 2 else "The refresh did not finish. Open the run link for details."
prog = read_json(out / "progress.json", {}) or {}
if prog.get("state") == "running" or state == "failed":
    prog.update(state=state, stage="done", message=message)
files = {"progress.json": json.dumps(prog, indent=1)}
cov = out / "coverage.json"
if cov.exists():
    files["coverage.json"] = cov.read_text(encoding="utf-8")
push_status(files)
