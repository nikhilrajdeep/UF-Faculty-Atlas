"""Crawl UF: colleges -> departments -> faculty pages -> individual faculty profiles + student lists."""
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from . import parsers as P
from .fetch import Fetcher
from .names import display_name, fold, last_name, name_key, squash
from .publish import push_status, read_json

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.getenv("ATLAS_OUT", ROOT / "docs" / "data"))
CATALOG_UNITS = "https://gradcatalog.ufl.edu/graduate/colleges-departments/"
CATALOG_ROSTER = "https://gradcatalog.ufl.edu/graduate/faculty/"

# Units the graduate catalog does not list, or whose catalog page has no usable website link.
EXTRA_UNITS = [
    {"college": "Levin College of Law", "name": "Levin College of Law", "site": "https://www.law.ufl.edu/",
     "hints": ["https://www.law.ufl.edu/faculty"]},
]
SITE_OVERRIDES = {
    "Soil, Water, and Ecosystem Sciences": "https://soils.ifas.ufl.edu/",
}

WORKERS_UNITS = int(os.getenv("ATLAS_UNIT_WORKERS", "10"))
WORKERS_PROFILES = int(os.getenv("ATLAS_PROFILE_WORKERS", "16"))
MAX_PROFILES_PER_UNIT = int(os.getenv("ATLAS_MAX_PROFILES_PER_UNIT", "1500"))


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def norm_unit(s):
    s = fold(s).replace("&", " and ")
    s = re.sub(r"\b(department|dept|school|college|division|program|of|the)\b", " ", s)
    return squash(re.sub(r"[^a-z0-9]+", " ", s))


def uid(*parts):
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


# ---------------------------------------------------------------- progress


class Progress:
    """Honest progress: percent comes from counted work (units done, profiles fetched), not elapsed time."""

    def __init__(self, local_dir):
        self.lock = threading.Lock()
        self.local_dir = Path(local_dir)
        self.t0 = time.time()
        self.state = {
            "state": "running", "stage": "starting", "message": "Starting", "percent": 0, "eta_seconds": None,
            "started_at": now_iso(), "updated_at": now_iso(),
            "run_url": (f"{os.getenv('GITHUB_SERVER_URL', 'https://github.com')}/{os.getenv('GITHUB_REPOSITORY', '')}/actions/runs/{os.getenv('GITHUB_RUN_ID', '')}"
                        if os.getenv("GITHUB_RUN_ID") else ""),
            "counts": {"units_total": 0, "units_done": 0, "profiles_total": 0, "profiles_done": 0,
                       "faculty": 0, "students": 0, "pages_fetched": 0},
        }
        self.last_publish = 0
        self.extra_files = {}

    def set(self, **kw):
        with self.lock:
            counts = kw.pop("counts", {})
            self.state["counts"].update(counts)
            self.state.update(kw)
            self.state["updated_at"] = now_iso()

    def bump(self, key, n=1):
        with self.lock:
            self.state["counts"][key] += n

    def compute(self):
        c = self.state["counts"]
        stage = self.state["stage"]
        if stage == "discover":
            pct = 1 + 4 * (c["units_done"] / c["units_total"] if c["units_total"] else 0)
        elif stage == "departments":
            pct = 5 + 15 * (c["units_done"] / c["units_total"] if c["units_total"] else 0)
        elif stage == "profiles":
            pct = 20 + 72 * (c["profiles_done"] / c["profiles_total"] if c["profiles_total"] else 1)
        elif stage == "merge":
            pct = 94
        else:
            pct = self.state["percent"]
        elapsed = time.time() - self.t0
        eta = None
        if 8 <= pct < 99:
            eta = int(elapsed * (100 - pct) / pct)
        with self.lock:
            self.state["percent"] = round(min(pct, 99.5), 1) if self.state["state"] == "running" else self.state["percent"]
            self.state["eta_seconds"] = eta

    def write(self, publish=False, force=False):
        self.compute()
        with self.lock:
            text = json.dumps(self.state, indent=1)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        (self.local_dir / "progress.json").write_text(text, encoding="utf-8")
        if publish and (force or time.time() - self.last_publish > 25):
            self.last_publish = time.time()
            files = {"progress.json": text, **self.extra_files}
            push_status(files)

    def finish(self, ok, message):
        with self.lock:
            self.state.update(state="success" if ok else "failed", stage="done", message=message,
                              percent=100 if ok else self.state["percent"], eta_seconds=0)
        self.write(publish=True, force=True)


def start_reporter(progress, stop):
    def loop():
        while not stop.is_set():
            progress.write(publish=True)
            stop.wait(10)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------- discovery


def discover_units(F, progress, only):
    page = F.get(CATALOG_UNITS)
    if not page:
        raise RuntimeError("UF graduate catalog unit list is unavailable; refusing to continue")
    units = P.parse_catalog_units(page[1], CATALOG_UNITS)
    if len(units) < 60:
        raise RuntimeError(f"Only {len(units)} units parsed from the catalog; the page layout may have changed")
    for u in units:
        u["id"] = uid(u["college"], u["name"])
        u["site"] = SITE_OVERRIDES.get(u["name"], "")
        u["hints"] = []
    units += [{**e, "id": uid(e["college"], e["name"]), "catalog_url": ""} for e in EXTRA_UNITS]
    if only:
        units = [u for u in units if any(o in u["name"].lower() or o in u["college"].lower() for o in only)]
    progress.set(stage="discover", message="Finding each department's website", counts={"units_total": len(units), "units_done": 0})

    def find_site(u):
        try:
            if not u["site"] and u.get("catalog_url"):
                res = F.get(u["catalog_url"])
                if res:
                    u["site"] = P.parse_unit_website(res[1], res[0])
        finally:
            progress.bump("units_done")

    with ThreadPoolExecutor(WORKERS_UNITS) as ex:
        list(ex.map(find_site, units))
    return units


def load_baseline(F):
    """Graduate-catalog roster: names, ranks and department labels for graduate faculty."""
    page = F.get(CATALOG_ROSTER)
    if page:
        rows = P.parse_catalog_roster(page[1])
        if len(rows) >= 100:
            return rows
    old = read_json(OUT / "faculty.json") or read_json(ROOT / "public" / "data" / "faculty.json") or {}
    return [{"name": display_name(f["name"]), "title": f.get("title", ""), "department": f.get("department", "")}
            for f in old.get("faculty", [])]


# ---------------------------------------------------------------- per-department people / students


def evaluate_listing(F, url, max_pages=30):
    """Parse a faculty listing page and its pagination. Returns (people, pages_used)."""
    people, seen_urls, queue, pages = {}, set(), [url], 0
    while queue and pages < max_pages:
        u = queue.pop(0)
        if u in seen_urls:
            continue
        seen_urls.add(u)
        res = F.get(u)
        if not res:
            continue
        pages += 1
        soup = P.make_soup(res[1])
        found = P.extract_people(soup, res[0])
        if len(found) < 3:
            found += [t for t in P.extract_table_people(soup) if t["name"] not in {f["name"] for f in found}]
        for p in found:
            key = p["profile_url"] or f"name:{name_key(p['name'])}"
            people.setdefault(key, p)
        queue.extend(n for n in P.next_pages(soup, res[0]) if n not in seen_urls)
    return list(people.values()), pages


def discover_unit(F, unit):
    """Find the unit's faculty list and student list. Returns a result dict."""
    info = {"site": unit["site"], "faculty_pages": [], "student_pages": [], "notes": []}
    res = {"unit": unit, "people": [], "students": [], "info": info}
    if not unit["site"]:
        info["notes"].append("no department website found on the catalog page")
        info["status"] = "no_site"
        return res
    home = F.get(unit["site"])
    if not home:
        info["notes"].append("department website did not load")
        info["status"] = "unreachable"
        return res
    home_url = home[0]
    soup = P.make_soup(home[1])
    cats = P.categorize_links(soup, home_url)
    fac, stu, hubs = list(cats["faculty"]), list(cats["students"]), list(cats["hub"])
    for h in hubs[:3]:
        page = F.get(h)
        if page:
            c2 = P.categorize_links(P.make_soup(page[1]), page[0])
            fac += c2["faculty"]
            stu += c2["students"]
            hubs_pages = c2["hub"]
            for h2 in hubs_pages[:2]:
                pg2 = F.get(h2)
                if pg2:
                    c3 = P.categorize_links(P.make_soup(pg2[1]), pg2[0])
                    fac += c3["faculty"]
                    stu += c3["students"]
    base = unit["site"] if unit["site"].endswith("/") else unit["site"] + "/"
    roots = [base]
    parsed = urlparse(base)
    if parsed.path not in ("", "/"):
        roots.append(f"{parsed.scheme}://{parsed.hostname}/")
    guesses = [urljoin(r, p) for p in P.PEOPLE_PATHS for r in roots]
    candidates = list(dict.fromkeys(unit.get("hints", []) + fac[:5] + hubs[:2] + guesses))

    best, tried = ([], 0), 0
    for cand in candidates:
        if tried >= 7:
            break
        people, pages = evaluate_listing(F, cand)
        tried += 1
        info["faculty_pages"].append({"url": cand, "people": len(people)})
        if len(people) > len(best[0]):
            best = (people, cand)
        if len(people) >= 10 and cand in fac + unit.get("hints", []):
            break
    res["people"] = best[0]
    info["chosen_faculty_page"] = best[1] if best[0] else ""

    # a 'People' hub may split faculty over category pages (Professors, Lecturers, ...): look one level deeper
    if len(best[0]) < 3 and best[1]:
        page = F.get(best[1])
        if page:
            extra = P.categorize_links(P.make_soup(page[1]), page[0])["faculty"][:6]
            merged = {p["profile_url"] or p["name"]: p for p in best[0]}
            for e in extra:
                if e == best[1]:
                    continue
                people, _ = evaluate_listing(F, e)
                info["faculty_pages"].append({"url": e, "people": len(people)})
                for p in people:
                    merged.setdefault(p["profile_url"] or p["name"], p)
            res["people"] = list(merged.values())

    # students
    stu_candidates = list(dict.fromkeys(stu[:4] + [urljoin(r, p) for p in P.STUDENT_PATHS for r in roots]))
    rows, tried = {}, 0
    for cand in stu_candidates:
        if tried >= 6:
            break
        if rows and cand not in stu:
            break
        tried += 1
        got, queue, seen = [], [cand], set()
        pages = 0
        while queue and pages < 20:
            u = queue.pop(0)
            if u in seen:
                continue
            seen.add(u)
            page = F.get(u)
            if not page:
                continue
            pages += 1
            sp = P.make_soup(page[1])
            got += P.parse_students(sp, page[0])
            queue.extend(n for n in P.next_pages(sp, page[0]) if n not in seen)
        info["student_pages"].append({"url": cand, "students": len(got)})
        for r in got:
            rows.setdefault(name_key(r["name"]), r)
    res["students"] = list(rows.values())
    info["status"] = "ok" if len(res["people"]) >= 3 else ("partial" if res["people"] else "no_people_page")
    if info["status"] == "no_people_page":
        info["notes"].append("no faculty list with individual profile links was recognised; graduate-catalog roster only")
    return res


# ---------------------------------------------------------------- profiles


def fetch_profile(F, task):
    """Fetch and parse one faculty profile; returns merged record fields."""
    person, unit = task["person"], task["unit"]
    url = person.get("profile_url")
    prof = None
    if url and urlparse(url).hostname:
        page = F.get(url)
        if page:
            prof = P.parse_profile(P.make_soup(page[1]), page[0], hint_name=person["name"])
            if prof and last_name(prof["name"]) != last_name(person["name"]):
                # wrong heading picked (e.g. department name): trust the listing card for identity fields
                prof["name"] = person["name"]
                prof["title"] = ""
    return prof


# ---------------------------------------------------------------- merge


def build_records(results, baseline, units):
    """Merge crawled people, profile details and the catalog roster into faculty records."""
    college_of = {norm_unit(u["name"]): u["college"] for u in units}
    by_profile, by_key = {}, {}
    records = []

    def new_record(name, unit):
        rec = {
            "id": "", "name": display_name(name), "title": "", "college": unit["college"] if unit else "",
            "department": unit["name"] if unit else "", "affiliations": [], "email": "", "research_areas": [],
            "research_summary": "", "teaching": [], "extension": [], "google_scholar": "", "orcid": "", "lab_name": "",
            "lab_url": "", "website": "", "edis_url": "", "profile_url": "", "location": "", "roles": [],
            "current_students": [], "sources": [], "verified_at": "",
        }
        if unit:
            rec["affiliations"].append({"college": unit["college"], "department": unit["name"]})
        records.append(rec)
        return rec

    for res in results:
        unit = res["unit"]
        for p in res["people"]:
            prof = p.get("profile") or {}
            purl = prof.get("profile_url") or p.get("profile_url") or ""
            key = name_key(p["name"])
            rec = by_profile.get(purl) if purl else None
            if rec is None:
                rec = by_key.get((key, unit["id"]))
            if rec is None:
                rec = new_record(prof.get("name") or p["name"], unit)
                by_key[(key, unit["id"])] = rec
            elif unit["name"] != rec["department"] and not any(a["department"] == unit["name"] for a in rec["affiliations"]):
                rec["affiliations"].append({"college": unit["college"], "department": unit["name"]})
            if purl:
                by_profile[purl] = rec
                rec["profile_url"] = rec["profile_url"] or purl
            for src, dst in (("title", "title"), ("email", "email"), ("location", "location")):
                v = prof.get(src) or p.get(src) or ""
                if v and not rec[dst]:
                    rec[dst] = v
            for k in ("google_scholar", "orcid", "lab_name", "lab_url", "website", "edis_url", "research_summary"):
                if prof.get(k) and not rec[k]:
                    rec[k] = prof[k]
            areas = list(prof.get("research_areas") or []) or list(p.get("specialty") or [])
            for fld, vals in (("research_areas", areas), ("teaching", prof.get("teaching") or []), ("extension", prof.get("extension") or []),
                              ("roles", p.get("roles") or [])):
                for v in vals:
                    if v and fold(v) not in {fold(x) for x in rec[fld]}:
                        rec[fld].append(v)
            rec["sources"] = list(dict.fromkeys(rec["sources"] + [u for u in (purl, res["info"].get("chosen_faculty_page")) if u]))
            rec["verified_at"] = now_iso() if prof or p.get("profile_url") else rec["verified_at"]
            rec["_profile_students"] = rec.get("_profile_students", []) + list(prof.get("profile_students") or [])
            by_key[(key, unit["id"])] = rec

    # Graduate-catalog roster: add anyone the department pages did not yield, and fill gaps for those it did.
    crawled_by_key = {}
    for r in records:
        crawled_by_key.setdefault(name_key(r["name"]), []).append(r)
    for b in baseline:
        key = name_key(b["name"])
        dept_norm = norm_unit(b.get("department", ""))
        match = None
        for r in crawled_by_key.get(key, []):
            if not dept_norm or norm_unit(r["department"]) == dept_norm or any(norm_unit(a["department"]) == dept_norm for a in r["affiliations"]):
                match = r
                break
        if match is None and len(crawled_by_key.get(key, [])) == 1 and not dept_norm:
            match = crawled_by_key[key][0]
        if match:
            if b.get("title") and not match["title"]:
                match["title"] = b["title"]
            if "https://gradcatalog.ufl.edu/graduate/faculty/" not in match["sources"]:
                match["sources"].append("https://gradcatalog.ufl.edu/graduate/faculty/")
            continue
        rec = new_record(b["name"], None)
        rec["title"] = b.get("title", "")
        rec["department"] = b.get("department", "")
        rec["college"] = college_of.get(dept_norm, "")
        if rec["college"]:
            rec["affiliations"].append({"college": rec["college"], "department": rec["department"]})
        rec["sources"] = ["https://gradcatalog.ufl.edu/graduate/faculty/"]
        crawled_by_key.setdefault(key, []).append(rec)

    for r in records:
        r["id"] = uid(r["profile_url"] or (name_key(r["name"]) + "|" + r["department"]))
    return records


def resolve_students(results, records):
    """Attach students to advisors by last name within the department; return student rows."""
    by_unit = {}
    for r in records:
        by_unit.setdefault(r["department"], []).append(r)
    students = []
    for res in results:
        unit = res["unit"]
        dept_faculty = by_unit.get(unit["name"], [])
        by_last = {}
        for f in dept_faculty:
            by_last.setdefault(last_name(f["name"]), []).append(f)
        for row in res["students"]:
            advisors, unresolved = [], []
            for tok in P.split_advisors(row.get("advisor_raw", "")):
                toks = fold(tok).split()
                cands = by_last.get(last_name(tok), []) if toks else []
                if len(cands) > 1 and len(toks) > 1:
                    cands = [c for c in cands if fold(c["name"]).startswith(toks[0][:1])] or cands
                if len(cands) == 1:
                    advisors.append(cands[0])
                else:
                    unresolved.append(tok)
            student = {
                "id": uid(unit["id"], name_key(row["name"])), "name": row["name"], "program": row.get("program", ""),
                "college": unit["college"], "department": unit["name"], "advisor_raw": row.get("advisor_raw", ""),
                "advisor_ids": [a["id"] for a in advisors], "advisor_names": [a["name"] for a in advisors] + unresolved,
                "research": row.get("research", ""), "lab": row.get("lab", ""), "source_url": row.get("source_url", ""),
            }
            students.append(student)
            for a in advisors:
                if name_key(row["name"]) not in {name_key(s["name"]) for s in a["current_students"]}:
                    a["current_students"].append({"name": row["name"], "program": row.get("program", "")})
    # students a professor lists on their own page
    for r in records:
        for s in r.pop("_profile_students", []):
            if name_key(s["name"]) not in {name_key(x["name"]) for x in r["current_students"]}:
                r["current_students"].append({"name": s["name"], "program": s.get("program", "")})
    for r in records:
        r.pop("_profile_students", None)
    return students


# ---------------------------------------------------------------- main


def run():
    only = [x.strip().lower() for x in os.getenv("ATLAS_ONLY", "").split(",") if x.strip()]
    budget = float(os.getenv("ATLAS_MAX_MINUTES", "300")) * 60
    OUT.mkdir(parents=True, exist_ok=True)
    progress = Progress(OUT)
    stop = threading.Event()
    F = Fetcher(delay=float(os.getenv("ATLAS_DELAY", "1.0")))
    t0 = time.time()
    reporter = start_reporter(progress, stop)
    try:
        units = discover_units(F, progress, only)
        baseline = load_baseline(F)
        progress.set(stage="departments", message=f"Reading faculty and student lists for {len(units)} departments",
                     counts={"units_done": 0, "units_total": len(units)})
        results = []

        def do_unit(u):
            try:
                if time.time() - t0 > budget * 0.25:
                    return {"unit": u, "people": [], "students": [], "info": {"site": u["site"], "status": "skipped_time", "notes": ["time budget"]}}
                return discover_unit(F, u)
            except Exception as e:  # keep the run alive; record it
                return {"unit": u, "people": [], "students": [], "info": {"site": u["site"], "status": "error", "notes": [f"{type(e).__name__}: {e}"[:200]]}}
            finally:
                progress.bump("units_done")

        with ThreadPoolExecutor(WORKERS_UNITS) as ex:
            results = list(ex.map(do_unit, units))

        # profile tasks, interleaved across hosts so slow sites do not block the rest
        queues = {}
        for res in results:
            for p in res["people"][:MAX_PROFILES_PER_UNIT]:
                if p.get("profile_url"):
                    host = urlparse(p["profile_url"]).hostname or ""
                    queues.setdefault(host, []).append({"person": p, "unit": res["unit"]})
        tasks = []
        while any(queues.values()):
            for h in list(queues):
                if queues[h]:
                    tasks.append(queues[h].pop(0))
        progress.set(stage="profiles", message=f"Reading {len(tasks)} faculty profile pages",
                     counts={"profiles_total": len(tasks), "profiles_done": 0,
                             "faculty": sum(len(r["people"]) for r in results),
                             "students": sum(len(r["students"]) for r in results)})
        skipped = [0]

        def do_profile(task):
            try:
                if time.time() - t0 > budget:
                    skipped[0] += 1
                    return
                task["person"]["profile"] = fetch_profile(F, task) or {}
            except Exception as e:
                task["person"]["profile"] = {}
                F.errors.append((task["person"].get("profile_url", ""), f"parse: {type(e).__name__}"))
            finally:
                progress.bump("profiles_done")
                progress.state["counts"]["pages_fetched"] = F.requests_made

        with ThreadPoolExecutor(WORKERS_PROFILES) as ex:
            list(ex.map(do_profile, tasks))

        progress.set(stage="merge", message="Merging records and matching students to advisors")
        records = build_records(results, baseline, units)
        students = resolve_students(results, records)
        write_outputs(records, students, results, units, F, progress, skipped[0], t0)
        progress.state["counts"].update(faculty=len(records), students=len(students))
        progress.finish(True, f"Updated {len(records)} faculty and {len(students)} students")
        return 0
    except Exception as e:
        progress.finish(False, f"{type(e).__name__}: {e}"[:300])
        raise
    finally:
        stop.set()


def write_outputs(records, students, results, units, F, progress, skipped, t0):
    stamp = now_iso()
    records.sort(key=lambda r: (last_name(r["name"]), r["name"]))
    students.sort(key=lambda s: (last_name(s["name"]), s["name"]))
    compact = dict(ensure_ascii=False, separators=(",", ":"))
    (OUT / "faculty.json").write_text(json.dumps({"metadata": {
        "updated_at": stamp, "total": len(records),
        "sources": ["https://gradcatalog.ufl.edu/graduate/faculty/", "UF department websites"],
        "note": "Compiled from public UF pages. Not an official UF product; verify details on the linked UF pages."},
        "faculty": records}, **compact), encoding="utf-8")
    (OUT / "students.json").write_text(json.dumps({"metadata": {"updated_at": stamp, "total": len(students)}, "students": students}, **compact), encoding="utf-8")

    cov_units, stat = [], {}
    for res in results:
        u, info = res["unit"], res["info"]
        mine = [r for r in records if r["department"] == u["name"] or any(a["department"] == u["name"] for a in r["affiliations"])]
        cov_units.append({
            "college": u["college"], "department": u["name"], "site": u["site"], "status": info.get("status", ""),
            "faculty_page": info.get("chosen_faculty_page", ""), "faculty_pages_tried": info.get("faculty_pages", [])[:8],
            "student_pages_tried": info.get("student_pages", [])[:6], "faculty_in_database": len(mine),
            "faculty_listed_on_site": len(res["people"]),
            "with_email": sum(bool(r["email"]) for r in mine), "with_scholar": sum(bool(r["google_scholar"]) for r in mine),
            "with_research": sum(bool(r["research_areas"]) for r in mine), "with_teaching": sum(bool(r["teaching"]) for r in mine),
            "students_found": len(res["students"]), "notes": info.get("notes", []),
        })
        stat[info.get("status", "")] = stat.get(info.get("status", ""), 0) + 1
    colleges = []
    for name in dict.fromkeys(u["college"] for u in units):
        cu = [c for c in cov_units if c["college"] == name]
        colleges.append({"name": name, "departments": len(cu), "faculty": sum(1 for r in records if r["college"] == name),
                         "departments_ok": sum(c["status"] == "ok" for c in cu)})
    coverage = {
        "updated_at": stamp, "elapsed_seconds": int(time.time() - t0), "pages_requested": F.requests_made,
        "status_counts": stat, "profiles_skipped_for_time": skipped, "colleges": colleges, "departments": cov_units,
        "totals": {
            "faculty": len(records), "students": len(students), "with_email": sum(bool(r["email"]) for r in records),
            "with_scholar": sum(bool(r["google_scholar"]) for r in records), "with_research": sum(bool(r["research_areas"]) for r in records),
            "with_teaching": sum(bool(r["teaching"]) for r in records), "with_students": sum(bool(r["current_students"]) for r in records),
            "with_college": sum(bool(r["college"]) for r in records),
        },
        "errors": [{"url": u, "error": e} for u, e in F.errors[:300]],
    }
    (OUT / "coverage.json").write_text(json.dumps(coverage, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "meta.json").write_text(json.dumps({"updated_at": stamp, "faculty": len(records), "students": len(students),
                                               "colleges": len(colleges), "departments": len(cov_units)}), encoding="utf-8")
    sample = random.Random(1).sample([r for r in records if r["profile_url"]], min(60, len([r for r in records if r["profile_url"]])))
    progress.extra_files = {
        "coverage.json": json.dumps(coverage, indent=1, ensure_ascii=False),
        "sample.json": json.dumps({"faculty": sample, "students": students[:40]}, indent=1, ensure_ascii=False),
    }


if __name__ == "__main__":
    sys.exit(run())
