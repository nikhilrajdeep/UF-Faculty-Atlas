"""Name and text normalisation helpers shared by the parsers and the merger."""
import re
import unicodedata

HONORIFIC = re.compile(r"^(dr|prof|professor|mr|mrs|ms|mx)\.?\s+", re.I)
CREDENTIALS = (
    r"ph\.?\s?d\.?|m\.?d\.?|m\.?s\.?c?\.?|d\.?v\.?m\.?|d\.?d\.?s\.?|j\.?d\.?|mba|m\.?p\.?h\.?|"
    r"p\.?e\.?|r\.?n\.?|dnp|aprn|cpa|faia|fasla|fasce|asla|aia|leed ap|esq\.?|jr\.?|sr\.?|ii|iii|iv"
)
TRAILING_CREDS = re.compile(r"(?:,|\s)\s*(?:" + CREDENTIALS + r")(?:\s*,\s*(?:" + CREDENTIALS + r"))*\.?\s*$", re.I)
PARTICLES = {
    "van", "von", "de", "del", "della", "der", "den", "da", "dos", "das", "di", "du", "la", "le",
    "bin", "al", "el", "ibn", "ten", "ter", "st", "st.", "y",
}
# Words that never appear in a person's name but often appear in navigation and headings.
STOP_WORDS = set("""
faculty staff department departments read more profile profiles contact students student graduate undergraduate
news events research about home people directory office center centre institute college school university
program programs page view all emeriti emeritus visit website email phone apply give login search menu skip main
content publications courses lab laboratory team group members alumni postdoctoral scholars lecturers professors
professor associate assistant adjunct sciences science studies engineering health medicine education florida
gainesville ufl uf ifas academic academics resources information services support careers jobs opportunities
administration administrative leadership board committee committees advisory council chair director dean provost
learn full bio biography cv curriculum vitae click here next previous back top skip learn explore welcome overview
mission history facts contacts location locations map directions parking calendar giving donate partners
sponsors funding grants awards honors news stories video videos gallery photos
""".split())
GENERIC_LINK_TEXT = re.compile(
    r"^(read more|more|view( full)?( profile| bio)?|profile|full profile|bio|biography|learn more|"
    r"website|web ?site|homepage|home page|details|see more|visit|cv|more info(rmation)?|about)\b",
    re.I,
)


def fold(text):
    """Lower-case ASCII fold for matching."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def squash(text):
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def clean_name(text):
    t = squash(text).strip(" ,;|-–—:")
    t = HONORIFIC.sub("", t)
    t = re.sub(r"\s*\([^)]*\)\s*", " ", t)  # nicknames and parentheticals
    t = squash(t)
    for _ in range(2):
        t = TRAILING_CREDS.sub("", t).strip(" ,;")
    return t


def looks_like_name(text):
    t = clean_name(text)
    if not t or len(t) > 60 or re.search(r"[\d@/:_=#|]", t):
        return False
    if "," in t:
        parts = [p.strip() for p in t.split(",")]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return False
        toks = parts[0].split() + parts[1].split()
    else:
        toks = t.split()
    if not 2 <= len(toks) <= 5:
        return False
    for w in toks:
        base = w.strip(".,")
        low = base.lower()
        if low in STOP_WORDS:
            return False
        if low in PARTICLES:
            continue
        if not re.match(r"^[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’.\-]*$", base):
            return False
    return True


def display_name(text):
    """'Last, First M.' -> 'First M. Last'; otherwise unchanged. Returns the cleaned name."""
    t = clean_name(text)
    if "," in t:
        last, first = [p.strip() for p in t.split(",", 1)]
        t = f"{first} {last}"
    return squash(t)


def name_tokens(text):
    t = fold(display_name(text))
    toks = [w.strip(".'’") for w in re.split(r"[\s]+", t) if w.strip(".'’")]
    return toks


def last_name(text):
    toks = name_tokens(text)
    if not toks:
        return ""
    i = len(toks) - 1
    while i > 0 and toks[i - 1] in PARTICLES:
        i -= 1
    return " ".join(toks[i:])


def first_name(text):
    toks = name_tokens(text)
    return toks[0] if toks else ""


def name_key(text):
    """first + last, ignoring middle names and initials, accents and credentials."""
    return f"{first_name(text)} {last_name(text)}".strip()
