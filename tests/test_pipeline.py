import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import test_parsers as T  # noqa: E402

CATALOG = """<main>%s</main>""" % "".join(
    f"<h2>{c}</h2><ul><li><a href='/graduate/colleges-departments/x/{i}/'>{n}</a></li></ul>"
    for i, (c, n) in enumerate([
        ("College of Agricultural and Life Sciences", "Soil, Water, and Ecosystem Sciences"),
        ("College of Dentistry", "Dentistry"),
    ] + [("College of Engineering", f"Dept {i}") for i in range(70)])
)
ROSTER = """<main><p>Babaeian, Ebrahim</p><p>Assistant Professor</p><p>Soil, Water, and Ecosystem Sciences</p>
<p>Bhadha, Jehangir</p><p>Associate Professor</p><p>Soil, Water, and Ecosystem Sciences</p>
<p>Zed, Zoe</p><p>Professor</p><p>Dentistry</p>""" + "".join(
    f"<p>Person{chr(65 + i % 26)}{i}, Name{chr(65 + i % 26)}</p><p>Professor</p><p>Dept 1</p>" for i in range(150)) + "</main>"

PAGES = {
    "https://gradcatalog.ufl.edu/graduate/colleges-departments/": CATALOG,
    "https://gradcatalog.ufl.edu/graduate/faculty/": ROSTER,
    "https://soils.ifas.ufl.edu/": "<html><body><nav><a href='/people/'>People</a></nav><main>home</main></body></html>",
    "https://soils.ifas.ufl.edu/people/": "<main><a href='/people/swes-faculty/'>Faculty</a><a href='/people/graduate-students/'>Graduate Students</a></main>",
    "https://soils.ifas.ufl.edu/people/swes-faculty/": T.IFAS_LIST,
    "https://soils.ifas.ufl.edu/people/faculty/jehangir-bhadha/": T.IFAS_PROFILE,
    "https://soils.ifas.ufl.edu/people/graduate-students/": T.STUDENTS,
}


class FakeFetcher:
    errors = []
    requests_made = 0

    def __init__(self, *a, **k):
        pass

    def get(self, url, keep=False):
        self.requests_made += 1
        if url in PAGES:
            return (url, PAGES[url])
        if "gradcatalog" in url and "/x/0/" in url:
            return (url, "<main><a href='https://soils.ifas.ufl.edu/'>https://soils.ifas.ufl.edu/</a></main>")
        if "/people/faculty/" in url:
            slug = url.rstrip("/").split("/")[-1]
            return (url, f"<main><h1>{slug.replace('-', ' ').title()}</h1><p>Professor</p><h3>Research</h3><ul><li>Topic of {slug}</li></ul></main>")
        return None


def test_end_to_end(monkeypatch):
    from atlas import crawl
    out = tempfile.mkdtemp()
    monkeypatch.setattr(crawl, "Fetcher", FakeFetcher)
    monkeypatch.setattr(crawl, "OUT", __import__("pathlib").Path(out))
    monkeypatch.setenv("ATLAS_ONLY", "soil")
    assert crawl.run() == 0
    fac = json.load(open(os.path.join(out, "faculty.json")))["faculty"]
    stu = json.load(open(os.path.join(out, "students.json")))["students"]
    cov = json.load(open(os.path.join(out, "coverage.json")))
    prog = json.load(open(os.path.join(out, "progress.json")))
    assert prog["state"] == "success" and prog["percent"] == 100
    bha = next(f for f in fac if f["name"] == "Jehangir Bhadha")
    assert bha["email"] == "jango@ufl.edu" and bha["google_scholar"].endswith("user=ABC123")
    assert bha["college"] == "College of Agricultural and Life Sciences"
    assert "Wetlands and Aquatic Ecosystems" in bha["research_areas"]
    assert {s["name"] for s in bha["current_students"]} == {"Xue Bai"}
    assert any(f["name"] == "Susan Crow" for f in fac)
    assert not any(f["name"] == "Footer Person" for f in fac)
    assert len(stu) == 4
    bai = next(s for s in stu if s["name"] == "Xue Bai")
    assert bai["program"] == "PhD" and bha["id"] in bai["advisor_ids"]
    assert "email" not in bai
    row = next(d for d in cov["departments"] if d["department"].startswith("Soil"))
    assert row["status"] == "ok" and row["faculty_listed_on_site"] == 4
