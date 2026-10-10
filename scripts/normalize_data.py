"""Apply common department names to an existing database folder (docs/data) without re-crawling.

usage: python scripts/normalize_data.py docs/data
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atlas.clean import COLLEGE_LABELS, DeptNames, canonicalize_records, strip_dept  # noqa: E402
from atlas.names import fold  # noqa: E402


def main(folder):
    d = Path(folder)
    fac_doc = json.loads((d / "faculty.json").read_text(encoding="utf-8"))
    stu_doc = json.loads((d / "students.json").read_text(encoding="utf-8"))
    cov = json.loads((d / "coverage.json").read_text(encoding="utf-8"))
    canon = DeptNames(x["department"] for x in cov["departments"])
    for x in cov["departments"]:
        x["department"] = canon(x["department"])
    for r in fac_doc["faculty"]:
        canon.add_label(r.get("department", ""))
        for a in r.get("affiliations", []):
            canon.add_label(a.get("department", ""))
    canonicalize_records(fac_doc["faculty"], canon)
    for r in fac_doc["faculty"]:
        if fold(r["department"]) in COLLEGE_LABELS:
            r["department"] = ""
        for a in r["affiliations"]:
            if fold(a.get("department", "")) in COLLEGE_LABELS:
                a["department"] = ""
        r["affiliations"] = list({(a.get("college", ""), a.get("department", "")): a for a in r["affiliations"]}.values())
    for s in stu_doc["students"]:
        s["department"] = canon(s["department"])
    for name, doc in (("faculty.json", fac_doc), ("students.json", stu_doc), ("coverage.json", cov)):
        (d / name).write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    meta_path = d / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["revision"] = hashlib.sha1((d / "faculty.json").read_bytes() + (d / "students.json").read_bytes()).hexdigest()[:10]
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    depts = {a["department"] for r in fac_doc["faculty"] for a in r["affiliations"] if a.get("department")}
    print(f"{len(fac_doc['faculty'])} faculty, {len(depts)} distinct departments; sample: {sorted(depts)[:5]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
