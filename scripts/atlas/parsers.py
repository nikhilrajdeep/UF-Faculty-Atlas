"""HTML parsers for UF department websites. Pure functions: no network access, easy to test."""
import re
from urllib.parse import parse_qs
from urllib.parse import urldefrag as _urldefrag
from urllib.parse import urljoin as _urljoin
from urllib.parse import urlparse as _urlparse

from bs4 import BeautifulSoup, Tag, NavigableString

from .names import (
    GENERIC_LINK_TEXT, clean_name, display_name, fold, last_name, looks_like_name, name_key, squash,
)

# Real pages contain malformed links (e.g. "http://[bad"); the stdlib raises ValueError on those.
def urlparse(u):
    try:
        return _urlparse(u)
    except ValueError:
        return _urlparse("")


def urljoin(base, u):
    try:
        return _urljoin(base, u)
    except ValueError:
        return ""


def urldefrag(u):
    try:
        return _urldefrag(u)
    except ValueError:
        return (u, "")


# ---------------------------------------------------------------- constants

TITLE_RE = re.compile(
    r"\b(professor|lecturer|instructor|scientist|scholar|researcher|curator|librarian|clinician|"
    r"extension agent|agent|faculty|chair|director|dean|emerit\w+|affiliate|adjunct|fellow|"
    r"physician|teaching)\b",
    re.I,
)
STAFF_RE = re.compile(
    r"\b(staff|administrative|secretary|assistant to|coordinator|technician|manager|analyst|programmer|"
    r"accountant|business|receptionist|specialist|student|postdoc\w*|post-doc\w*|intern|fiscal|"
    r"communications|webmaster|it support|advisor)\b",
    re.I,
)
LOCATION_RE = re.compile(
    r"\b(REC|R\.E\.C\.|research (and|&) education center|research center|station|campus|building|hall|"
    r"room|po box|gainesville|lab\b|laboratory|institute|center\b)",
    re.I,
)
ROLE_RE = re.compile(r"\b(chair|coordinator|director|head|associate dean|graduate program)\b", re.I)
GENERIC_EMAIL_LOCALS = {
    "info", "contact", "webmaster", "admin", "office", "dept", "department", "help", "support", "web",
    "communications", "news", "events", "advising", "undergrad", "grad", "gradinfo", "chair", "dean",
    "admissions", "hr", "it", "marketing", "ufit", "helpdesk", "feedback", "noreply", "no-reply",
}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@(?:[A-Za-z0-9\-]+\.)+[A-Za-z]{2,}")
OBFUSCATED_EMAIL_RE = re.compile(
    r"([A-Za-z0-9._%+\-]+)\s*(?:\[at\]|\(at\)|\{at\}|\bat\b)\s*((?:[A-Za-z0-9\-]+\s*(?:\[dot\]|\(dot\)|\.)\s*)+[A-Za-z]{2,})",
    re.I,
)
SKIP_EXT = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|zip|jpe?g|png|gif|svg|mp4|mp3|css|js|ico)$", re.I)
SKIP_LINK_PATH = re.compile(
    r"/(news|events?|tag|tags|category|categories|author|calendar|search|login|wp-content|feed|"
    r"alumni|students?|graduate-students|undergraduate|apply|give|donate|publications?)(/|$)",
    re.I,
)

H_RESEARCH = re.compile(
    r"^(research|research\s+(interests?|areas?|focus|summary|programs?|expertise|overview|description|and\s+scholarship)|"
    r"areas?\s+of\s+(research|expertise|interest|specialization|specialty)|expertise|(current\s+)?(research\s+)?interests?|"
    r"program\s+areas?|specializations?|scholarly\s+interests|research\s+topics?|current\s+research)$",
    re.I,
)
H_TEACH = re.compile(
    r"^(teaching|courses?(\s+taught)?|classes(\s+taught)?|current\s+courses|instruction|"
    r"teaching\s+(interests?|responsibilities|assignments?|areas?|activities)|courses\s+offered)$",
    re.I,
)
H_EXT = re.compile(
    r"^(extension|extension\s+(programs?|activities|focus|areas?|and\s+outreach|education|work)|"
    r"outreach|outreach\s+and\s+engagement|extension\s+and\s+outreach|public\s+engagement|extension\s+programs?\s+and\s+resources)$",
    re.I,
)
H_STUDENTS = re.compile(
    r"^(current\s+)?((graduate|grad|phd|ph\.d\.|ms|m\.s\.|masters?|master'?s|doctoral|undergraduate|postdoc\w*|postdoctoral)\s+)*"
    r"(students?|advisees|(lab|group|research\s+group|team)\s+members|(lab|group)\s+(people|personnel)|"
    r"my\s+(students|team|group)|current\s+(group|team|lab)|lab\s+personnel|people|team|group)$",
    re.I,
)
H_GENERIC_DROP = re.compile(r"^(research|program areas?|publications?|read more|more|teaching|extension|contact.*)$", re.I)
LABEL_RE = {
    "research": re.compile(
        r"^(research(?:\s+(?:interests?|areas?|focus|program))?|areas?\s+of\s+(?:research|expertise)|interests?|expertise|specializations?)\s*[:\-–—]\s*(.{3,})$",
        re.I,
    ),
    "teaching": re.compile(r"^(teaching|courses?(?:\s+taught)?|classes\s+taught)\s*[:\-–—]\s*(.{3,})$", re.I),
    "extension": re.compile(r"^(extension(?:\s+(?:focus|programs?|areas?))?)\s*[:\-–—]\s*(.{3,})$", re.I),
}
COURSE_RE = re.compile(r"\b([A-Z]{3}\s?\d{4}[A-Z]?)\b\s*[:\-–—]?\s*([A-Z][^.;|\n]{3,80})?")
ADVISOR_LABEL = re.compile(r"(?:co-?)?(?:advisor|adviser|major\s+professor|supervisor|mentor|chair|advised\s+by)s?\s*[:\-–—]?\s*", re.I)

PEOPLE_PATHS = [
    "people/", "faculty/", "people/faculty/", "directory/", "about/people/", "faculty-staff/",
    "people/faculty-staff/", "our-people/", "about/faculty/", "people/directory/", "faculty-and-staff/",
    "people/our-faculty/", "faculty-directory/", "about-us/people/", "about/directory/", "people/professors/",
]
STUDENT_PATHS = [
    "people/graduate-students/", "graduate-students/", "students/", "people/students/", "graduate/students/",
    "academics/graduate-students/", "people/grad-students/", "people/current-students/", "current-students/",
    "graduate/current-students/", "people/phd-students/", "about/people/graduate-students/",
]

# ---------------------------------------------------------------- soup helpers


def make_soup(html):
    return BeautifulSoup(html or "", "lxml")


def _is_chrome(el, mode="strict"):
    """True for site chrome that never contains profile content.

    Some UF sites mislabel their whole page body with role="navigation" or leave <main> empty, so 'loose' mode
    only trusts real <nav>/<footer> tags.
    """
    if el.name in ("script", "style", "noscript", "svg", "iframe", "select", "option", "template", "nav", "footer"):
        return True
    if mode == "loose":
        return False
    if el.name == "form":
        ident = " ".join(el.get("class", [])) + " " + (el.get("id") or "") + " " + (el.get("role") or "")
        return bool(el.find("input", attrs={"type": "search"})) or "search" in ident.lower()
    role = (el.get("role") or "").lower()
    if role in ("navigation", "banner", "contentinfo", "search"):
        return True
    ident = " ".join(el.get("class", [])) + " " + (el.get("id") or "")
    if el.name == "header" and (el.find("nav") or re.search(r"site-header|masthead|global|top-?bar", ident, re.I)):
        return True
    if re.search(r"\b(breadcrumbs?|skip-?link|cookie|mega-?menu|main-menu|site-footer|footer-links)\b", ident, re.I):
        return True
    return False


def content_root(soup):
    return soup.select_one("main") or soup.select_one("[role=main]") or soup.select_one("article") or \
        soup.select_one("#content") or soup.select_one("#main") or soup.body or soup


def visible_text(el, sep="\n"):
    if el is None:
        return ""
    parts = []
    for node in el.descendants:
        if isinstance(node, NavigableString):
            p = node.parent
            if p is not None and p.name in ("script", "style", "noscript", "template"):
                continue
            s = str(node)
            if s.strip():
                parts.append(squash(s))
    return sep.join(parts)


BLOCK_TAGS = {"p", "div", "ul", "ol", "table", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "dl", "blockquote"}
ACCORDION_CLS = re.compile(r"(accordion|collaps|panel|tab|toggle|expand)[-_ ]?(title|header|heading|toggle|trigger|button|link)|accordion-?title|js-toggle", re.I)


def blocks(root, mode="strict"):
    """Flatten content into a token stream: ('h', level, text) | ('li', text) | ('p', text) | ('row', [cells])."""
    out = []

    def has_block_child(el):
        return any(isinstance(c, Tag) and c.name in BLOCK_TAGS for c in el.children)

    def walk(el):
        for ch in el.children:
            if not isinstance(ch, Tag):
                continue
            if _is_chrome(ch, mode):
                continue
            name = ch.name
            cls = " ".join(ch.get("class", []))
            if re.fullmatch(r"h[1-6]", name):
                t = squash(ch.get_text(" ", strip=True))
                if t:
                    out.append(("h", int(name[1]), t))
                continue
            if name in ("summary", "dt", "button") or ch.get("role") in ("tab", "button") or (
                cls and ACCORDION_CLS.search(cls) and len(ch.get_text(strip=True)) < 90
            ):
                t = squash(ch.get_text(" ", strip=True))
                if t and len(t) < 90:
                    out.append(("h", 5, t))
                    continue
            if name == "table":
                for tr in ch.find_all("tr"):
                    cells = [squash(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
                    if any(cells):
                        out.append(("row", cells))
                continue
            if name == "li":
                nested = ch.find(["ul", "ol"])
                own = squash("".join(
                    c.get_text(" ", strip=True) + " " if isinstance(c, Tag) and c.name not in ("ul", "ol") else str(c)
                    for c in ch.children if not (isinstance(c, Tag) and c.name in ("ul", "ol"))
                ))
                if own:
                    out.append(("li", own))
                if nested:
                    walk(ch)
                continue
            if name in ("p", "div", "span", "section", "article", "dd", "blockquote", "td"):
                if not has_block_child(ch) and not ch.find(["ul", "ol", "li", "table"]):
                    t = squash(ch.get_text(" ", strip=True))
                    if t:
                        strong = ch.find(["strong", "b"])
                        if strong and squash(strong.get_text(" ", strip=True)) == t and len(t) <= 60:
                            out.append(("h", 6, t.rstrip(": ")))
                        else:
                            out.append(("p", t))
                    continue
            walk(ch)

    walk(root)
    return out


def sections(tokens):
    secs, cur = [], {"title": "", "level": 0, "items": []}
    for t in tokens:
        if t[0] == "h":
            secs.append(cur)
            cur = {"title": t[2], "level": t[1], "items": []}
        else:
            cur["items"].append(t)
    secs.append(cur)
    return secs


def _section_lines(secs, idx):
    """Text lines of a section plus its deeper child sections (e.g. 'Program areas' -> 'Research')."""
    base = secs[idx]
    lines = [_item_text(i) for i in base["items"]]
    j = idx + 1
    while j < len(secs) and secs[j]["level"] > base["level"] > 0 and secs[j]["level"] != 0:
        lines.extend(_item_text(i) for i in secs[j]["items"])
        j += 1
    return [l for l in lines if l]


def _item_text(item):
    if item[0] == "row":
        return " | ".join(c for c in item[1] if c)
    if item[0] == "h":
        return item[2]
    return item[1]


AREA_PREFIX = re.compile(
    r"^(research(\s+(interests?|areas?|focus|program))?|areas?\s+of\s+(research|expertise)|interests?|expertise|specializations?)\s*[:\-–—]\s*",
    re.I,
)


def _split_areas(lines, limit=15):
    areas, summary = [], ""
    for line in lines:
        line = AREA_PREFIX.sub("", squash(line))
        if not line or H_GENERIC_DROP.match(line):
            continue
        if re.match(r"^(select\s+)?publications?\b", line, re.I):
            continue
        if len(line) > 160:
            if not summary:
                summary = line[:700]
            continue
        for part in re.split(r"\s*[;•|]\s*", line):
            part = part.strip(" .,-–")
            if 2 < len(part) <= 120 and not H_GENERIC_DROP.match(part):
                areas.append(part)
    seen, out = set(), []
    for a in areas:
        k = fold(a)
        if k not in seen:
            seen.add(k)
            out.append(a)
    return out[:limit], summary


def _inline_labels(tokens):
    found = {"research": [], "teaching": [], "extension": []}
    for t in tokens:
        if t[0] not in ("p", "li"):
            continue
        for key, rx in LABEL_RE.items():
            m = rx.match(t[1])
            if m:
                found[key].append(m.group(2))
    return found


# ---------------------------------------------------------------- links, emails


def canon_url(url, base=None, keep_query_keys=("id", "uid", "netid", "user", "person", "profile", "pid", "faculty")):
    if not url:
        return ""
    url = url.strip()
    if url.startswith(("mailto:", "tel:", "javascript:", "#", "data:")):
        return ""
    full = urljoin(base or "", url)
    full, _ = urldefrag(full)
    p = urlparse(full)
    if p.scheme not in ("http", "https") or not p.hostname:
        return ""
    qs = parse_qs(p.query)
    keep = {k: v for k, v in qs.items() if k.lower() in keep_query_keys}
    query = "&".join(f"{k}={v[0]}" for k, v in keep.items())
    host = p.hostname.lower()
    netloc = host + (f":{p.port}" if p.port and p.port not in (80, 443) else "")
    return f"https://{netloc}{p.path or '/'}" + (f"?{query}" if query else "")


def is_uf_host(host):
    host = (host or "").lower()
    return host == "ufl.edu" or host.endswith(".ufl.edu")


def canon_scholar(href):
    p = urlparse(href)
    uid = parse_qs(p.query).get("user")
    if uid:
        return f"https://scholar.google.com/citations?user={uid[0]}"
    return f"https://{p.hostname}{p.path}" + (f"?{p.query}" if p.query else "")


def _text_outside_chrome(el):
    parts = []
    for node in el.descendants:
        if isinstance(node, NavigableString):
            if any(p.name in ("footer", "nav", "script", "style", "noscript", "template") for p in node.parents):
                continue
            if str(node).strip():
                parts.append(str(node).strip())
    return " ".join(parts)


GENERIC_LOCAL_RE = re.compile(
    r"^(?:.*[-_.])?(webmaster|info|admin|office|contact|noreply|no-reply|helpdesk|support|dept|department|news|events|"
    r"advising|admissions|communications|frontdesk|reception|registrar|feedback|marketing)(?:[-_.0-9].*)?$"
)


def find_emails(el):
    """Unique e-mail addresses in an element: mailto links first, then plain and obfuscated text. Ignores footer/nav."""
    if el is None:
        return []
    found = []
    for a in el.select('a[href^="mailto:"]'):
        if a.find_parent(["footer", "nav"]):
            continue
        addr = a["href"][7:].split("?")[0].strip().replace("%20", "")
        if EMAIL_RE.fullmatch(addr):
            found.append(addr.lower())
    text = _text_outside_chrome(el)
    found += [m.group(0).lower() for m in EMAIL_RE.finditer(text)]
    for m in OBFUSCATED_EMAIL_RE.finditer(text):
        dom = re.sub(r"\s*(\[dot\]|\(dot\))\s*", ".", m.group(2), flags=re.I).replace(" ", "")
        found.append(f"{m.group(1)}@{dom}".lower())
    out = []
    for a in found:
        if a not in out:
            out.append(a)
    return out


def pick_email(emails, person_name=""):
    last, first = last_name(person_name), (fold(display_name(person_name)).split() or [""])[0]
    best, best_score = "", -1
    for e in emails:
        local, _, domain = e.partition("@")
        if local in GENERIC_EMAIL_LOCALS or GENERIC_LOCAL_RE.match(local):
            continue
        score = 0
        l = fold(local)
        if last and last.replace(" ", "") in l:
            score += 3
        if first and (l.startswith(first[:1]) and last and last.split()[-1][:4] in l):
            score += 2
        if domain.endswith("ufl.edu"):
            score += 1
        if score > best_score:
            best, best_score = e, score
    return best


# ---------------------------------------------------------------- profile page


def _profile_score(r):
    if not r:
        return -1
    return sum(bool(r[k]) for k in ("email", "research_areas", "teaching", "google_scholar", "title", "extension", "lab_url", "orcid"))


def parse_profile(soup, url, hint_name=""):
    """Extract one faculty member's details from their individual page.

    Tries the page's main content first; if that finds little (some sites leave <main> empty or mislabel their
    whole body as navigation) it retries on the whole body and keeps the richer result.
    """
    best = _parse_profile(soup, url, hint_name, "strict")
    if _profile_score(best) < 3:
        loose = _parse_profile(soup, url, hint_name, "loose")
        if _profile_score(loose) > _profile_score(best):
            best = loose
    return best


def _parse_profile(soup, url, hint_name, mode):
    root = content_root(soup) if mode == "strict" else (soup.body or soup)
    toks = blocks(root, mode)
    secs = sections(toks)

    # --- name
    name = ""
    for t in toks:
        if t[0] == "h" and t[1] <= 3 and looks_like_name(t[2]):
            name = display_name(t[2])
            break
    if not name:
        title_tag = squash(soup.title.get_text()) if soup.title else ""
        first_seg = re.split(r"\s+[-|–—]\s+", title_tag)[0]
        if looks_like_name(first_seg):
            name = display_name(first_seg)
    if not name and hint_name:
        name = display_name(hint_name)
    if not name:
        return None

    # --- title: first title-like short line shortly after the name
    title = ""
    lines = [_item_text(t) for t in toks if t[0] in ("p", "li", "h")]
    name_idx = next((i for i, l in enumerate(lines) if fold(name.split()[-1]) in fold(l) and len(l) < 80), 0)
    for l in lines[name_idx: name_idx + 8]:
        if len(l) < 140 and TITLE_RE.search(l) and not looks_like_name(l):
            title = l
            break
        if len(l) < 140 and TITLE_RE.search(l) and looks_like_name(l) is False:
            title = l
            break

    # --- sections
    research, teaching, extension, students = [], [], [], []
    summary = ""
    for i, s in enumerate(secs):
        h = s["title"]
        if not h:
            continue
        if H_RESEARCH.match(h):
            ls = _section_lines(secs, i)
            a, sm = _split_areas(ls)
            research += a
            summary = summary or sm
        elif H_TEACH.match(h):
            teaching += [l for l in _section_lines(secs, i) if 2 < len(l) <= 200]
        elif H_EXT.match(h):
            extension += [l for l in _section_lines(secs, i) if 2 < len(l) <= 240]
        elif H_STUDENTS.match(h):
            for l in _section_lines(secs, i):
                st = parse_student_line(l)
                if st:
                    students.append(st)
    labels = _inline_labels(toks)
    for v in labels["research"]:
        a, sm = _split_areas([v])
        research += a
        summary = summary or sm
    teaching += [v for v in labels["teaching"] if len(v) <= 240]
    extension += [v for v in labels["extension"] if len(v) <= 240]

    def dedupe(seq, cap):
        seen, out = set(), []
        for x in seq:
            k = fold(x)
            if k and k not in seen:
                seen.add(k)
                out.append(x)
        return out[:cap]

    # --- contact + links
    emails = find_emails(root)
    for extra in soup.select("aside, .sidebar, [class*=contact], [class*=sidebar]"):
        if not _is_chrome(extra, mode):
            emails += [e for e in find_emails(extra) if e not in emails]
    email = pick_email(emails, name)
    if not email and len([e for e in emails if not GENERIC_LOCAL_RE.match(e.split("@")[0])]) == 1:
        email = next(e for e in emails if not GENERIC_LOCAL_RE.match(e.split("@")[0]))

    scholar = orcid = lab_url = lab_name = website = edis = ""
    for a in soup.select("a[href]"):
        if a.find_parent(["nav", "footer"]):
            continue
        href = canon_url(a["href"], url) if not a["href"].startswith("mailto:") else ""
        if not href:
            continue
        text = squash(a.get_text(" ", strip=True))
        host = urlparse(href).hostname or ""
        if "scholar.google." in host and not scholar:
            scholar = canon_scholar(a["href"] if a["href"].startswith("http") else href)
        elif "orcid.org" in host and not orcid:
            orcid = href
        elif host == "edis.ifas.ufl.edu" and "author" in href.lower() + text.lower() or (host == "edis.ifas.ufl.edu" and re.search(r"topic_a|publications", href + text, re.I)):
            edis = edis or href
        elif not lab_url and re.search(r"\b(lab|laboratory|research group|group)\b", text, re.I) and not re.search(r"scholar|google|linkedin|twitter|facebook|researchgate", host):
            if urlparse(href).path.rstrip("/") != urlparse(url).path.rstrip("/"):
                lab_url, lab_name = href, text[:80]
        elif not website and re.search(r"^(personal\s+)?(web ?site|home ?page)\b|\bpersonal (web)?site\b", text, re.I):
            website = href

    return {
        "name": name,
        "title": title,
        "email": email,
        "research_areas": dedupe(research, 15),
        "research_summary": summary,
        "teaching": dedupe(teaching, 20),
        "extension": dedupe(extension, 15),
        "profile_students": students[:60],
        "google_scholar": scholar,
        "orcid": orcid,
        "lab_url": lab_url,
        "lab_name": lab_name,
        "website": website,
        "edis_url": edis,
        "profile_url": url,
    }


def parse_student_line(line):
    """'Jane Doe (PhD)' / 'Doe, Jane - MS' -> {name, program} if the line is a student entry."""
    line = squash(line)
    prog = ""
    m = re.search(r"\(?\b(ph\.?\s?d\.?|doctoral|ms|m\.s\.|master'?s?|postdoc\w*|undergraduate|b\.s\.)\b\)?", line, re.I)
    if m:
        prog = _program(m.group(1))
        line = squash(line.replace(m.group(0), " "))
    line = re.split(r"\s+[-–—|]\s+|\s*\(|\s*,\s*(?=[a-z])", line)[0] if not re.match(r"^[^,]+,\s*[A-Z]", line) else line
    line = line.strip(" ,;:-")
    if looks_like_name(line):
        return {"name": display_name(line), "program": prog}
    return None


def _program(text):
    t = fold(text)
    if re.search(r"ph|doctor", t):
        return "PhD"
    if re.search(r"^m\.?s|master", t):
        return "MS"
    if "postdoc" in t:
        return "Postdoc"
    if "undergrad" in t or t.startswith("b"):
        return "Undergraduate"
    return ""


# ---------------------------------------------------------------- listing pages


def _nearest_name_for_link(a, text):
    """Name for an anchor: its own text, aria/title attribute, image alt, or the card's heading."""
    if looks_like_name(text):
        return display_name(text), True
    for attr in ("aria-label", "title"):
        v = a.get(attr) or ""
        v = re.sub(r"^(view|read|visit|go to)\s+(the\s+)?(profile|bio|page)?\s*(for|of)?\s*", "", v, flags=re.I)
        if looks_like_name(v):
            return display_name(v), True
    img = a.find("img")
    if img and img.get("alt"):
        alt = img["alt"]
        m = re.search(r"(?:headshot|photo|picture|portrait|image)\s+of\s+(?:dr\.?\s+)?([^,.–—]+)", alt, re.I)
        cand = m.group(1) if m else alt
        if looks_like_name(cand):
            return display_name(cand), False
    if GENERIC_LINK_TEXT.match(text) or not text:
        node = a
        for _ in range(4):
            node = node.parent
            if node is None or node.name in ("body", "main"):
                break
            for h in node.find_all(["h1", "h2", "h3", "h4", "h5", "strong", "b"], limit=4):
                ht = squash(h.get_text(" ", strip=True))
                if looks_like_name(ht):
                    return display_name(ht), False
    return "", False


def extract_people(soup, base_url, accept_hosts=None):
    """People on a listing page that link to individual profile pages.

    Returns a list of dicts: name, profile_url, lines (card text), email, title, specialty, location, roles.
    Tries the main content first, then the whole body (some UF pages put the list outside <main>).
    """
    best = []
    for mode in ("strict", "loose"):
        root = content_root(soup) if mode == "strict" else (soup.body or soup)
        people = _extract_people(root, base_url, accept_hosts, mode)
        if len(people) >= 3:
            return people
        if len(people) > len(best):
            best = people
    return best


def _extract_people(root, base_url, accept_hosts, mode):
    base_host = urlparse(base_url).hostname or ""
    base_path = urlparse(base_url).path.rstrip("/")
    cands = {}
    for a in root.select("a[href]"):
        if _inside_chrome(a, root, mode):
            continue
        url = canon_url(a["href"], base_url)
        if not url:
            continue
        pu = urlparse(url)
        if not is_uf_host(pu.hostname) or SKIP_EXT.search(pu.path):
            continue
        if accept_hosts is not None and pu.hostname not in accept_hosts:
            continue
        if pu.path.rstrip("/") == base_path and pu.hostname == base_host:
            continue
        text = squash(a.get_text(" ", strip=True))
        name, strong = _nearest_name_for_link(a, text)
        if not name:
            continue
        c = cands.setdefault(url, {"name": name, "strong": strong, "anchor": a})
        if strong and not c["strong"]:
            c.update(name=name, strong=True, anchor=a)

    groups = {}
    for url, c in cands.items():
        pu = urlparse(url)
        if pu.query:
            key = (pu.hostname, pu.path)
        else:
            key = (pu.hostname, pu.path.rsplit("/", 2)[0] + "/" if pu.path.count("/") >= 2 else "/")
        groups.setdefault(key, []).append(url)
    if not groups:
        return []
    best = max(len(v) for v in groups.values())
    chosen = []
    for key, urls in groups.items():
        if SKIP_LINK_PATH.search(key[1]):
            continue
        if len(urls) >= 3 and len(urls) >= 0.25 * best or best < 3:
            chosen.extend(urls)

    people, seen_names = [], {}
    for url in chosen:
        c = cands[url]
        card = _card_for(c["anchor"], c["name"], cands)
        lines = [l for l in card["lines"] if fold(c["name"]) not in fold(l) and fold(clean_name(c["name"])) != fold(l)]
        title = next((l for l in lines if TITLE_RE.search(l) and len(l) < 120), "")
        rest = [l for l in lines if l != title]
        loc = next((l for l in rest if LOCATION_RE.search(l) and len(l) < 100), "")
        roles = [l for l in rest if ROLE_RE.search(l) and len(l) < 100]
        specialty = [l for l in rest if l != loc and l not in roles and len(l) < 120 and "@" not in l and not re.search(r"\d{3}[-.)\s]\d{3,4}", l)]
        rec = {
            "name": c["name"], "profile_url": url, "lines": lines[:6], "email": pick_email(card["emails"], c["name"]),
            "title": title, "specialty": specialty[:3], "location": loc, "roles": roles[:2],
        }
        key = name_key(c["name"])
        if key in seen_names:  # same person linked twice (photo + name) with different URLs: keep the first
            continue
        seen_names[key] = rec
        people.append(rec)
    return [p for p in people if _plausible_faculty(p)]


def _plausible_faculty(p):
    t = p["title"] or " ".join(p["lines"][:2])
    if not t:
        return True
    if TITLE_RE.search(t):
        return True
    return not STAFF_RE.search(t)


def _inside_chrome(a, root, mode="strict"):
    for parent in a.parents:
        if parent is root:
            return False
        if parent.name in ("nav", "footer"):
            return True
        if mode == "strict" and (parent.get("role") or "") in ("navigation", "contentinfo", "banner"):
            return True
    return False


def _card_for(anchor, name, cands):
    """Smallest ancestor containing this person but no other candidate person link."""
    others = {id(c["anchor"]) for c in cands.values() if c["anchor"] is not anchor}
    node, best = anchor, anchor
    for _ in range(5):
        parent = node.parent
        if parent is None or parent.name in ("body", "main", "html"):
            break
        if any(id(a) in others for a in parent.find_all("a", href=True)):
            break
        node = best = parent
    lines = [l for l in (squash(s) for s in best.get_text("\n", strip=True).split("\n")) if l]
    return {"lines": lines, "emails": find_emails(best)}


def extract_table_people(soup):
    """People rows from tables without profile links: header-mapped name/title/email/areas."""
    out = []
    for tbl in soup.find_all("table"):
        head = [fold(squash(th.get_text(" ", strip=True))) for th in tbl.select("thead th, tr:first-child th")]
        if not head:
            continue
        idx = {k: i for i, h in enumerate(head) for k, rx in
               {"name": r"\bname\b|faculty|person", "title": r"title|rank|position", "email": r"e-?mail",
                "research": r"research|interest|expertise|area|specialt", "phone": r"phone"}.items() if re.search(rx, h)}
        if "name" not in idx:
            continue
        for tr in tbl.select("tbody tr") or tbl.find_all("tr")[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= idx["name"]:
                continue
            raw = squash(cells[idx["name"]].get_text(" ", strip=True))
            if not looks_like_name(raw):
                continue
            row = {"name": display_name(raw), "profile_url": "", "lines": [], "title": "", "specialty": [], "location": "", "roles": []}
            if "title" in idx and idx["title"] < len(cells):
                row["title"] = squash(cells[idx["title"]].get_text(" ", strip=True))
            row["email"] = ""
            if "email" in idx and idx["email"] < len(cells):
                es = find_emails(cells[idx["email"]])
                row["email"] = es[0] if es else ""
            if "research" in idx and idx["research"] < len(cells):
                row["specialty"] = _split_areas([squash(cells[idx["research"]].get_text("; ", strip=True))])[0]
            a = cells[idx["name"]].find("a", href=True)
            row["profile_url"] = canon_url(a["href"]) if a else ""
            out.append(row)
    return out


# ---------------------------------------------------------------- navigation


def categorize_links(soup, base_url):
    """Find likely faculty-list, student-list and hub ('People') links on a page."""
    base_host = urlparse(base_url).hostname
    fac, stu, hub = [], [], []
    for a in soup.select("a[href]"):
        url = canon_url(a["href"], base_url)
        if not url:
            continue
        pu = urlparse(url)
        if not is_uf_host(pu.hostname) or SKIP_EXT.search(pu.path):
            continue
        text = fold(squash(a.get_text(" ", strip=True)))
        path = pu.path.lower()
        if len(text) > 60:
            continue
        hay = f"{text} {path}"
        if re.search(r"prospective|apply|admission|alumni|undergrad|how to|handbook|resources|forms|news|event|seminar|job|career|award|opportunit", hay):
            continue
        if re.search(r"\b(graduate|grad|phd|ph\.d\.|doctoral|masters?|current)\b.{0,12}\bstudents?\b|/(graduate-students|grad-students|phd-students|current-students|students)/?$", hay) or text in ("students", "our students", "student directory"):
            stu.append(url)
        elif re.search(r"\b(faculty|professors|investigators|researchers)\b", text) and "emerit" not in text and "staff" not in text.replace("faculty & staff", "faculty"):
            fac.append(url)
        elif re.search(r"\b(faculty|professors)\b", path) and not re.search(r"/(news|events?)/", path) and path.count("/") <= 4:
            fac.append(url)
        elif re.search(r"^(people|our people|directory|faculty (and|&) staff|faculty/staff|faculty-staff|meet (the )?(faculty|our team)|personnel)$", text) or re.search(r"/(people|directory|personnel)/?$", path):
            hub.append(url)
    def uniq(seq):
        return list(dict.fromkeys(seq))
    return {"faculty": uniq(fac), "students": uniq(stu), "hub": uniq(hub)}


def next_pages(soup, url):
    """Pagination links belonging to the same listing."""
    p = urlparse(url)
    out = []
    for a in soup.select("a[href]"):
        href = a["href"]
        full = urljoin(url, href)
        fp = urlparse(full)
        if fp.hostname != p.hostname:
            continue
        text = squash(a.get_text(" ", strip=True)).lower()
        rel = " ".join(a.get("rel", [])) if a.get("rel") else ""
        aria = (a.get("aria-label") or "").lower()
        paged = re.search(r"([?&](page|pg|paged|p)=\d+)|(/page/\d+/?$)", full)
        if ("next" in rel or text in ("next", "next page", "›", "»", "next ›", "next »") or "next" in aria or
                (paged and fp.path.rstrip("/").split("/page/")[0] == p.path.rstrip("/").split("/page/")[0] and text.isdigit())):
            full = urldefrag(full)[0]
            if full != url and full not in out:
                out.append(full)
    return out[:40]


# ---------------------------------------------------------------- students (department level)


def _heading_before(el):
    node = el
    for _ in range(40):
        node = node.find_previous(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "caption"])
        if node is None:
            return ""
        t = squash(node.get_text(" ", strip=True))
        if t and len(t) < 80 and not re.fullmatch(r"search:?", t, re.I):
            return t
    return ""


def parse_students(soup, url):
    """Student rows from department 'graduate students' pages: tables, then headed lists."""
    out = []
    for tbl in soup.find_all("table"):
        head = [fold(squash(th.get_text(" ", strip=True))) for th in tbl.select("thead th, tr:first-child th")]
        idx = {}
        for i, h in enumerate(head):
            for key, rx in (("name", r"\bname\b|student"), ("advisor", r"advis|major prof|mentor|supervis|chair"),
                            ("program", r"degree|program|level|track"), ("research", r"research|topic|thesis|project|interest|dissertation"),
                            ("lab", r"\blab\b|group")):
                if key not in idx and re.search(rx, h):
                    idx[key] = i
        if "name" not in idx:
            continue
        group = _program(_heading_before(tbl)) or _program(squash(tbl.find("caption").get_text()) if tbl.find("caption") else "")
        rows = tbl.select("tbody tr") or tbl.find_all("tr")[1:]
        for tr in rows:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= idx["name"]:
                continue
            raw = squash(cells[idx["name"]].get_text(" ", strip=True))
            if not looks_like_name(raw):
                continue
            def cell(key):
                i = idx.get(key)
                return squash(cells[i].get_text(" ", strip=True)) if i is not None and i < len(cells) else ""
            out.append({
                "name": display_name(raw), "program": _program(cell("program")) or group,
                "advisor_raw": cell("advisor"), "research": cell("research"), "lab": cell("lab"), "source_url": url,
            })
    if out:
        return out

    toks = blocks(content_root(soup))
    group = ""
    pending = None
    for t in toks:
        if t[0] == "h":
            group = _program(t[2]) or group
            pending = None
            continue
        text = _item_text(t)
        m = ADVISOR_LABEL.search(text)
        st = parse_student_line(text) if not m else None
        if st:
            adv = ""
            paren = re.search(r"\(([^)]*(?:advis|mentor|with)[^)]*)\)", text, re.I)
            if paren:
                adv = ADVISOR_LABEL.sub("", paren.group(1)).replace("with", "").strip(" ,;")
            pending = {"name": st["name"], "program": st["program"] or group, "advisor_raw": adv, "research": "", "lab": "", "source_url": url}
            out.append(pending)
        elif m and pending is not None and not pending["advisor_raw"]:
            pending["advisor_raw"] = squash(text[m.end():])
        elif m:
            # 'Jane Doe - Advisor: Smith' on a single line
            left = text[:m.start()].strip(" -–—|,:()")
            if looks_like_name(left):
                out.append({"name": display_name(left), "program": group, "advisor_raw": squash(text[m.end():]),
                            "research": "", "lab": "", "source_url": url})
    return out


def split_advisors(raw):
    """'Bhadha & Smidt', 'Daroub (Temp)', 'Kadyampakeni and Nunes' -> ['Bhadha', 'Smidt']"""
    raw = re.sub(r"\([^)]*\)", " ", raw or "")
    raw = re.sub(r"\bamp;", "&", raw)
    parts = re.split(r"\s*(?:&|/|;|\band\b|\+|,)\s*", raw)
    return [squash(p) for p in parts if squash(p) and len(squash(p)) > 1]


# ---------------------------------------------------------------- graduate catalog (baseline roster + unit pages)

CATALOG_RANK = re.compile(
    r"^(?:(?:Distinguished|Assistant|Associate|Research|Clinical|Courtesy|Adjunct|Affiliate|Emeritus|Visiting|Full|Senior|Master)\s+)*"
    r"(?:Professor|Lecturer|Scientist|Instructor|Curator|Scholar|Researcher|Engineer|Librarian)(?:\b.*)?$",
    re.I,
)


def parse_catalog_roster(html):
    """Faculty rows from gradcatalog.ufl.edu/graduate/faculty/: 'Last, First' / rank / department lines."""
    soup = make_soup(html)
    main = soup.select_one("#content") or soup.select_one("main") or soup
    for t in main.select("script,style,nav,footer,aside"):
        t.decompose()
    lines = [squash(s) for s in main.get_text("\n", strip=True).splitlines()]
    lines = [s for s in lines if s]
    out = {}
    for i, name in enumerate(lines[:-2]):
        if "," not in name or not 4 <= len(name) <= 100 or re.search(r"\d|https?://", name):
            continue
        cands = lines[i + 1:i + 5]
        pos = next((j for j, t in enumerate(cands) if len(t) < 80 and CATALOG_RANK.match(t)), None)
        if pos is None:
            continue
        dept = ""
        if pos + 1 < len(cands):
            poss = cands[pos + 1]
            if len(poss) < 120 and not CATALOG_RANK.match(poss) and "," not in poss:
                dept = poss
        out[re.sub("[^a-z0-9]", "", name.lower())] = {"name": display_name(name), "catalog_name": name, "title": cands[pos], "department": dept}
    return list(out.values())


def parse_catalog_units(html, root_url):
    """(college, unit name, unit URL) from the catalog's colleges-departments page."""
    soup = make_soup(html)
    body = soup.select_one("#content") or soup.select_one("main") or soup
    college, units, seen = None, [], set()
    for el in body.find_all(["h2", "li"]):
        if el.name == "h2":
            t = squash(el.get_text(" ", strip=True))
            college = t if re.match(r"^(College of|Warrington College|Herbert Wertheim College|Levin College)", t) else None
        elif college:
            a = el.find("a", href=True)
            if not a:
                continue
            name = squash(a.get_text(" ", strip=True))
            link = canon_url(a["href"], root_url)
            if name and link and (college, name) not in seen:
                seen.add((college, name))
                units.append({"college": college, "name": name, "catalog_url": link})
    return units


CATALOG_SKIP_HOSTS = {
    "gradcatalog.ufl.edu", "campusmap.ufl.edu", "www.ufl.edu", "ufl.edu", "grad.ufl.edu", "registrar.ufl.edu",
    "catalog.ufl.edu", "admissions.ufl.edu", "gradschool.ufl.edu", "www.grad.ufl.edu",
}


def parse_unit_website(html, page_url):
    """Department website: first external UF link on a catalog unit page (prefers 'website' wording)."""
    soup = make_soup(html)
    body = soup.select_one("#content") or soup.select_one("main") or soup
    cands = []
    for a in body.select("a[href]"):
        url = canon_url(a["href"], page_url)
        if not url:
            continue
        host = urlparse(url).hostname
        if host in CATALOG_SKIP_HOSTS or not is_uf_host(host):
            continue
        text = fold(squash(a.get_text(" ", strip=True)))
        weight = 2 if re.search(r"website|more info|department|school|http|\.ufl\.edu|home", text) else 1
        cands.append((weight, url))
    if not cands:
        return ""
    cands.sort(key=lambda c: -c[0])
    return cands[0][1]
