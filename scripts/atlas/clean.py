"""Final clean-up of merged faculty records: drops page furniture that parsers let through,
repairs department/college labels and removes e-mail addresses that belong to someone else."""
import html
import re

from .names import fold, last_name, first_name, name_key, name_tokens, squash

FACULTY_WORD = re.compile(
    r"professor|lecturer|instructor|faculty|scientist|researcher|fellow|emerit|chair|scholar|dean|investigator|clinician|"
    r"physician|librarian|curator|coach|artist|engineer|specialist in|agent", re.I)
STAFF_TITLE = re.compile(
    r"\b(director of (finance|it|operations|development|engagement|communications|admissions|student)|it director|"
    r"coordinator|manager|administrator|analyst|secretary|accountant|buyer|payroll|human resources|"
    r"program assistant|office assistant|business manager|fiscal|budget|technician|webmaster|receptionist)\b", re.I)
BARE_STAFF = re.compile(r"^(director|assistant director|associate director|executive director|senior director)\b", re.I)

# Labels used by the graduate catalog roster that are not unit names on the catalog's college page.
LABEL_COLLEGE = {
    "veterinary medicine": "College of Veterinary Medicine",
    "journalism and communications": "College of Journalism and Communications",
    "neuroscience": "College of Medicine",
    "neuroscience (idp)": "College of Medicine",
    "biomedical engineering": "Herbert Wertheim College of Engineering",
    "nursing": "College of Nursing",
    "construction management": "College of Design, Construction and Planning",
    "sociology and criminology & law": "College of Liberal Arts and Sciences",
    "sociology and criminology and law": "College of Liberal Arts and Sciences",
    "physical therapy": "College of Public Health and Health Professions",
    "occupational therapy": "College of Public Health and Health Professions",
    "environmental horticulture": "College of Agricultural and Life Sciences",
    "fisheries and aquatic sciences": "College of Agricultural and Life Sciences",
    "agricultural and life sciences": "College of Agricultural and Life Sciences",
    "medicine": "College of Medicine",
    "accounting": "Warrington College of Business",
    "business": "Warrington College of Business",
    "dentistry": "College of Dentistry",
    "oral biology": "College of Dentistry",
    "pharmacology and therapeutics (idp)": "College of Medicine",
    "physiology and aging (idp)": "College of Medicine",
    "anatomy and cell biology": "College of Medicine",
    "biochemistry and molecular biology (idp)": "College of Medicine",
    "genetics (idp)": "College of Medicine",
    "genetics and genomics": "College of Medicine",
    "clinical investigation (idp)": "College of Medicine",
    "latin american studies": "College of Liberal Arts and Sciences",
    "liberal arts and sciences": "College of Liberal Arts and Sciences",
    "romance languages and literatures": "College of Liberal Arts and Sciences",
    "public health and health professions": "College of Public Health and Health Professions",
    "behavioral science and community health": "College of Public Health and Health Professions",
    "communication sciences and disorders": "College of Public Health and Health Professions",
    "pharmacodynamics": "College of Pharmacy",
    "pharmacy": "College of Pharmacy",
    "education": "College of Education",
    "digital worlds": "College of the Arts",
    "arts": "College of the Arts",
    "law": "Levin College of Law",
    "comparative law": "Levin College of Law",
    "engineering": "Herbert Wertheim College of Engineering",
}

LABEL_JUNK = re.compile(
    r"^(department|email|e-mail|phone|fax|office|orcid|profile|other|all faculty|affiliate faculty|primary faculty|"
    r"emeritus faculty|affiliations?|faculty|dr\.?|mr\.?|ms\.?|mrs\.?|prof\.?|ph\.?d\.?|m\.?s\.?|m\.?d\.?|b\.?s\.?|"
    r"read more|view profile|learn more|website|cv|curriculum vitae|publications?|google scholar|links?|research|"
    r"research interests?|areas? of (research|interest|expertise)|teaching|courses|contact( information)?|bio(graphy)?|"
    r"education|honors?( and awards)?|awards?|degrees?|more|details?|none|n/a|tbd)\s*:?$", re.I)
HR_CODE = re.compile(r"^[A-Z]{2,6}(?:-[A-Z0-9&,.() ]{2,}){1,3}$")  # e.g. "PHHP-COM BIOSTATISTICS", "HP-PHYSICAL THERAPY"
COURSE_CODE = re.compile(r"\b[A-Z]{3,4}\s?\d{4}[A-Z]?\b")
TEACH_JUNK = re.compile(
    r"course title|identifier|frequency|manage consent|search|submit|mailing address|office hours|phone|email|@|"
    r"privacy|cookie|skip to|copyright|all rights|login|menu|subscribe|follow us", re.I)


def unescape(s):
    return squash(html.unescape(s or "")) if isinstance(s, str) else s


def _own_name_bits(rec):
    return {t for t in name_tokens(rec["name"]) if len(t) > 1}


UNIT_NAMES = set()  # filled by finalize(): every department / college label, so listing categories are not research areas


def clean_areas(rec):
    own = _own_name_bits(rec)
    dept_fold = {fold(rec.get("department", "")), fold(rec.get("college", ""))}
    for a in rec.get("affiliations", []):
        dept_fold.update({fold(a.get("department", "")), fold(a.get("college", ""))})
    out, seen = [], set()
    for raw in rec.get("research_areas", []):
        a = unescape(raw).strip(" -–—•·|;,")
        f = fold(a)
        if not a or len(a) < 3 or len(a) > 140 or f in seen:
            continue
        if LABEL_JUNK.match(a) or a.endswith(":") or HR_CODE.match(a):
            continue
        if re.search(r"@|https?://|\bphone\b|\bemail\b|\d{3}[-.\s]\d{3,4}", a, re.I):
            continue
        if f in dept_fold or any(f == d or f == "department of " + d for d in dept_fold if d):
            continue
        toks = set(re.findall(r"[a-z]+", f))
        if toks and toks <= own | {"dr", "prof"}:
            continue
        if re.fullmatch(r"(ph\.?d\.?|m\.?s\.?|m\.?d\.?|b\.?s\.?)[:\s]*(student)?", f):
            continue
        if a.isupper() and len(a) > 3 and " " in a or re.fullmatch(r"[A-Z]{4,}", a):
            continue  # HR codes and abbreviations: "CLIN AST PROF", "INTERNET"
        if re.search(r"faculty profile|search|submit|committee|adjunct faculty|affiliate and|^uf |^university of florida|"
                     r"^school of |^college of |^department of |^center for |^institute for ", a, re.I):
            continue
        if f in UNIT_NAMES:
            continue
        if re.match(r"^(m\.?s\.?|ph\.?d\.?|b\.?s\.?|b\.?a\.?|m\.?a\.?|pharm\.?d\.?|d\.?v\.?m\.?|j\.?d\.?|m\.?b\.?a\.?)\s*[:.,]?(\s|$)", a, re.I):
            continue  # degree lines from a CV: "M.S.: University of Florida, Animal Sciences"
        if re.search(r"\b(assistant|associate|emeritus|distinguished|clinical|research|courtesy|adjunct|affiliate)?\s*professors?\b( of| emerit\w+)?", f) and len(f.split()) <= 5:
            continue
        if re.fullmatch(r"home ?page|no photo available|courses taught|mentor|mentors|personal website|lab website|lab page", f):
            continue
        seen.add(f)
        out.append(a)
    return out


def clean_teaching(rec, extra=()):
    out, seen = [], set()
    for raw in list(rec.get("teaching", [])) + list(extra):
        t = unescape(raw).strip(" -–—•·|;,")
        f = fold(t)
        if not t or len(t) < 4 or len(t) > 160 or f in seen or TEACH_JUNK.search(t):
            continue
        if not COURSE_CODE.search(t) and (len(t.split()) > 14 or t.endswith(":") or LABEL_JUNK.match(t)):
            continue
        seen.add(f)
        out.append(t)
    return out


def clean_title(rec):
    t = unescape(rec.get("title", ""))
    t = re.sub(r"^(affiliations?)\s+", "", t, flags=re.I).strip(" ,;:|-–—")
    t = re.sub(r"\s+\S+(?:\s\S+)?['’]s\s+[\w&]+\s+(?:profile|page|website)(?:\s+page)?\s*$", "", t, flags=re.I).strip(" ,;:|-–—")
    if len(t) > 140 or "collection of websites" in t.lower() or t.startswith(":"):
        t = ""
    if re.search(r"graduate faculty status|dean'?s office$", t, re.I):
        t = ""
    return t


NOT_A_PERSON = {
    "schedule", "consultation", "canvas", "info", "information", "abroad", "assists", "center", "centre", "services", "support",
    "office", "help", "request", "apply", "contact", "resources", "registration", "scholarship", "scholarships", "calendar", "faq",
    "faqs", "policy", "policies", "guide", "handbook", "training", "workshop", "workshops", "tutorial", "events", "news",
    "directory", "portal", "system", "technology", "it", "admissions", "advising", "career", "careers", "internship", "internships",
    "giving", "donate", "alumni", "study", "login", "welcome", "consulting", "lab", "program", "programs", "department", "institute",
}


def is_not_a_person(rec):
    toks = set(re.findall(r"[a-z]+", fold(rec["name"])))
    return bool(toks & NOT_A_PERSON) or len(rec["affiliations"]) >= 8 and not rec.get("title") and not rec.get("email")


def is_staff(rec):
    t = rec.get("title", "")
    if not t or FACULTY_WORD.search(t):
        return False
    return bool(STAFF_TITLE.search(t) or BARE_STAFF.match(t))


def _email_matches(rec, email):
    local = fold(email.split("@")[0])
    local = re.sub(r"[^a-z]", "", local)
    last, first = re.sub(r"[^a-z]", "", last_name(rec["name"])), re.sub(r"[^a-z]", "", first_name(rec["name"]))
    if not local:
        return False
    return (len(last) >= 3 and last in local) or (len(first) >= 3 and first in local and len(local) >= len(first)) or \
        (first and last and local.startswith(first[0]) and local[1:].startswith(last[:3]))


def fix_shared_emails(records):
    """An address shared by several different people is a department contact picked up from a page; keep it only
    for the person whose name it matches (or nobody)."""
    by_email = {}
    for r in records:
        if r["email"]:
            by_email.setdefault(r["email"].lower(), []).append(r)
    fixed = 0
    for email, group in by_email.items():
        if len({last_name(r["name"]) + "|" + first_name(r["name"])[:1] for r in group}) < 2:
            continue
        for r in group:
            if not _email_matches(r, email):
                r["email"] = ""
                fixed += 1
    # a single record whose e-mail clearly belongs to nobody by that name is left alone (courtesy/affiliate addresses vary)
    return fixed


def finalize(records, units):
    """Mutates and returns the list of kept records."""
    college_names = sorted({u["college"] for u in units})
    UNIT_NAMES.clear()
    for u in units:
        UNIT_NAMES.update({fold(u["name"]), _norm_unit(u["name"]), fold(u["college"])})
        UNIT_NAMES.add(re.sub(r"\s+department$", "", fold(u["name"])))
    records = merge_duplicates(records)
    dept_college = {}
    for u in units:
        dept_college.setdefault(fold(u["name"]), u["college"])
    kept = []
    for r in records:
        for k in ("department", "college", "location", "lab_name", "research_summary"):
            r[k] = unescape(r.get(k, ""))
        r["title"] = clean_title(r)
        r["research_summary"] = re.sub(r"^Research Departmental Program Areas:.*?Research focus:\s*", "", r.get("research_summary", ""), flags=re.I)
        r["roles"] = [unescape(x) for x in r.get("roles", []) if unescape(x)]
        for a in r.get("affiliations", []):
            a["department"], a["college"] = unescape(a.get("department", "")), unescape(a.get("college", ""))
        if r["department"] and not r["college"]:
            label = fold(r["department"])
            col = dept_college.get(label) or LABEL_COLLEGE.get(label)
            if not col:
                col = next((c for c in college_names if label and label in fold(c)), "")
            if col:
                r["college"] = col
                if not r["affiliations"]:
                    r["affiliations"].append({"college": col, "department": r["department"]})
                else:
                    for a in r["affiliations"]:
                        if not a.get("college"):
                            a["college"] = col
        if len(r["department"]) <= 2:  # truncated label such as "L"
            r["department"] = ""
        courses = [re.sub(r"^teaching[:\s]+", "", a, flags=re.I) for a in r.get("research_areas", []) if COURSE_CODE.search(a)]
        r["research_areas"] = clean_areas({**r, "research_areas": [a for a in r.get("research_areas", []) if not COURSE_CODE.search(a)]})
        r["teaching"] = clean_teaching(r, courses)
        r["extension"] = [e for e in (unescape(x) for x in r.get("extension", [])) if e and not TEACH_JUNK.search(e) and len(e) < 200]
        if is_not_a_person(r):
            continue
        if is_staff(r) and not r["research_areas"] and not r["google_scholar"]:
            continue
        r.pop("_cat_dept", None)
        kept.append(r)
    fix_shared_emails(kept)
    return kept


def _norm_unit(s):
    s = fold(s).replace("&", " and ")
    s = re.sub(r"\b(department|dept|school|college|division|program|of|the)\b", " ", s)
    return squash(re.sub(r"[^a-z0-9]+", " ", s))


def _richness(r):
    return (bool(r.get("profile_url")), len(r.get("research_areas", [])) + len(r.get("teaching", [])), bool(r.get("email")))


def _same_person(a, b):
    """Records are grouped by first+last name already; two different e-mail addresses mean two people."""
    ea, eb = (a.get("email") or "").lower(), (b.get("email") or "").lower()
    return not (ea and eb) or ea == eb


def _combine(cluster):
    p = cluster[0]
    for o in cluster[1:]:
        for k in ("title", "email", "location", "google_scholar", "orcid", "lab_name", "lab_url", "website", "edis_url",
                  "profile_url", "research_summary", "verified_at", "_cat_dept"):
            if o.get(k) and not p.get(k):
                p[k] = o[k]
        for k in ("research_areas", "teaching", "extension", "roles", "sources"):
            have = {fold(x) for x in p.get(k, [])}
            p[k] = list(p.get(k, [])) + [x for x in o.get(k, []) if fold(x) not in have]
        have = {fold(x.get("name", "")) for x in p.get("current_students", [])}
        p["current_students"] = list(p.get("current_students", [])) + [x for x in o.get("current_students", []) if fold(x.get("name", "")) not in have]
        p["affiliations"] = list(p.get("affiliations", [])) + list(o.get("affiliations", []))
        p["_profile_students"] = list(p.get("_profile_students", [])) + list(o.get("_profile_students", []))
    # Affiliations that only came from a college-wide people page say nothing about the department:
    # keep them only when the graduate catalog (or a department's own page) confirms them.
    affs, seen = [], set()
    for a in p.get("affiliations", []):
        k = (a.get("college", ""), _norm_unit(a.get("department", "")))
        if k not in seen:
            seen.add(k)
            affs.append(a)
    cat = _norm_unit(p.get("_cat_dept", ""))
    solid = [a for a in affs if not a.get("shared") or (cat and _norm_unit(a.get("department", "")) == cat)]
    if not solid and affs:
        colleges = {a.get("college", "") for a in affs}
        solid = [{"college": colleges.pop(), "department": ""}] if len(colleges) == 1 else []
    for a in solid:
        a.pop("shared", None)
    p["affiliations"] = solid
    if solid:
        p["college"], p["department"] = solid[0].get("college", ""), solid[0].get("department", "")
    elif cat and p.get("_cat_dept"):
        p["department"] = p["_cat_dept"]
    return p


def merge_duplicates(records):
    groups = {}
    for r in records:
        groups.setdefault(name_key(r["name"]), []).append(r)
    out = []
    for grp in groups.values():
        clusters = []
        for r in sorted(grp, key=_richness, reverse=True):
            for cl in clusters:
                if all(_same_person(c, r) for c in cl):
                    cl.append(r)
                    break
            else:
                clusters.append([r])
        out.extend(_combine(cl) for cl in clusters)
    return out


STUDENT_JUNK = re.compile(
    r"\b(forms?|syllabus|paper|registration|certificates?|handbook|polic(?:y|ies)|assistance|financial|committee|requirements?|"
    r"applications?|deadlines?|checklist|guidelines?|templates?|orientation|tuition|scholarships?|fellowships?|curriculum|courses?|"
    r"schedule|calendar|resources?|information|credit|unique|degrees?|thesis|dissertation|exams?|defense|advising|seminar|"
    r"travel|funding|opportunit\w+|study|professional|graduate|undergraduate|students?|faculty|staff|program|department)\b", re.I)
BUILDING = re.compile(r"\b(hall|building|bldg|center|centre|library|room)\b\s*\d*$", re.I)


SENTENCE_WORDS = re.compile(r"\b(this|that|who|welcome|congratulations|joined|joins)\b", re.I)


def student_name_ok(name):
    n = squash(name)
    return bool(n) and not STUDENT_JUNK.search(n) and not BUILDING.search(n) and not re.match(r"^(dr|prof|professor)\b\.?", n, re.I) \
        and not SENTENCE_WORDS.search(n)


def clean_students(students):
    out = []
    for s in students:
        if not student_name_ok(s.get("name", "")):
            continue
        s["advisor_names"] = [a for a in (squash(x) for x in s.get("advisor_names", []))
                              if a and a[0].isupper() and len(a) > 2 and not STUDENT_JUNK.search(a)]
        out.append(s)
    return out
