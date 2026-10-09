import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from atlas import parsers as P  # noqa: E402
from atlas.names import display_name, looks_like_name, name_key  # noqa: E402

# Structure observed on soils.ifas.ufl.edu (IFAS "complex layout" cards).
IFAS_LIST = """
<html><body><div id="top-nav-wrapper"><nav><a href="/people/">People</a><a href="/people/graduate-students/">Graduate Students</a></nav></div>
<main><div class="row"><div class="complex-layout large-12 medium-12">
 <span></span><div class="complex-content large-4 medium-4">
   <p><a href="/people/faculty/ebrahim-babaeian/"><img alt="A headshot of Ebrahim Babaeian, SWES assistant professor." src="x.jpg"></a></p>
   <p><a href="/people/faculty/ebrahim-babaeian/">Ebrahim Babaeian</a></p><p>Assistant Professor</p><p>Soil Physics</p></div>
 <span></span><div class="complex-content large-4 medium-4">
   <p><a href="/people/faculty/jehangir-bhadha/">Jehangir Bhadha</a></p><p>Associate Professor</p><p>Soil, Water, and Nutrient Management</p><p>Everglades REC</p></div>
 <span></span><div class="complex-content large-4 medium-4">
   <p><a href="/people/faculty/james-bonczek/">James Bonczek</a></p><p>Undergraduate Coord. and Sr. Lecturer</p><p>Soil and Water Sciences</p></div>
 <span></span><div class="complex-content large-4 medium-4">
   <p><a href="/people/faculty/susan-crow/">Susan Crow</a></p><p>Department Chair and Professor</p><p>Soil Ecology and Biogeochemistry</p></div>
</div></div></main><footer><a href="/people/faculty/footer-person/">Footer Person</a></footer></body></html>
"""

IFAS_PROFILE = """
<html><head><title>Jehangir Bhadha - Department of Soil, Water, and Ecosystem Sciences - UF/IFAS</title></head><body>
<nav><a href="/x/">menu</a></nav>
<main><h1>Soil, Water, and Ecosystem Sciences</h1><p>Faculty &gt;</p>
<h2>Jehangir Bhadha</h2><p>Associate Professor, Soil, Water Nutrient Management</p><p>Everglades Research and Education Center</p>
<p><a href="https://erec.ifas.ufl.edu/people/bhadha/">Jehangir Bhadha's EREC Profile Page</a></p>
<h3>Program areas</h3>
<div class="accordion"><a class="accordion-title" href="#">Research</a><div class="accordion-content"><ul><li>Nutrient, Pesticide, and Waste Management</li><li>Wetlands and Aquatic Ecosystems</li></ul></div></div>
<p>Research focus: Water quality, soil sustainability; sustainable agriculture</p>
<h3>Publications</h3><div><a class="accordion-title">Select Publications 2025-Present</a><div>Some paper.</div></div>
<p><a href="https://scholar.google.com/citations?user=ABC123&hl=en">Jehangir Bhadha on Google Scholar</a></p>
<p><a href="https://edis.ifas.ufl.edu/topic_a-bhadhajh">Jehangir Bhadha EDIS Publications</a></p>
<h4>CONTACT INFORMATION</h4><p>UF/IFAS Everglades REC, Belle Glade</p><p><a href="mailto:jango@ufl.edu">jango@ufl.edu</a></p>
</main><footer><a href="mailto:swes-webmaster@ufl.edu">Webmaster</a></footer></body></html>
"""

STUDENTS = """
<main><h3>MS Students</h3><table class="sortable stack dataTable"><thead><tr><th>NAME</th><th></th><th>ADVISOR</th><th>LOCATION</th></tr></thead>
<tbody><tr><td><em>Alvarez, Maria</em></td><td>mj.alvarez@ufl.edu</td><td>Daroub (Temp)</td><td>Florida Tamarac</td></tr>
<tr><td><em>Batts, Carly</em></td><td>cbatts1@ufl.edu</td><td>Lusk</td><td>Florida Jensen Beach</td></tr></tbody></table>
<h3>PhD Students</h3><table class="sortable stack dataTable"><thead><tr><th>NAME</th><th></th><th>ADVISOR</th><th>LOCATION</th></tr></thead>
<tbody><tr><td><em>Bai, Xue</em></td><td>bai.xue@ufl.edu</td><td>Bhadha &amp; Smidt</td><td>Florida Everglades REC - Belle Glade</td></tr>
<tr><td><em>Agunbiade, Labake Ogunkanmi</em></td><td>x@ufl.edu</td><td>Kadyampakeni amp; Nunes</td><td>Lake Alfred</td></tr></tbody></table></main>
"""


def test_names():
    assert looks_like_name("Ebrahim Babaeian")
    assert looks_like_name("Dr. Susan Crow, Ph.D.")
    assert looks_like_name("Alvarez, Maria")
    assert looks_like_name("Jean-Luc O'Neil")
    assert looks_like_name("Ana de la Cruz")
    assert not looks_like_name("Read More")
    assert not looks_like_name("Faculty Directory")
    assert not looks_like_name("Graduate Students")
    assert display_name("Bai, Xue") == "Xue Bai"
    assert name_key("Aaron, Jessica Elana") == name_key("Jessica E. Aaron")


def test_listing_cards():
    people = P.extract_people(P.make_soup(IFAS_LIST), "https://soils.ifas.ufl.edu/people/swes-faculty/")
    names = [p["name"] for p in people]
    assert names == ["Ebrahim Babaeian", "Jehangir Bhadha", "James Bonczek", "Susan Crow"], names
    bha = people[1]
    assert bha["title"] == "Associate Professor"
    assert "Soil, Water, and Nutrient Management" in bha["specialty"]
    assert bha["location"] == "Everglades REC"
    assert bha["profile_url"] == "https://soils.ifas.ufl.edu/people/faculty/jehangir-bhadha/"


def test_profile():
    r = P.parse_profile(P.make_soup(IFAS_PROFILE), "https://soils.ifas.ufl.edu/people/faculty/jehangir-bhadha/")
    assert r["name"] == "Jehangir Bhadha"
    assert "Associate Professor" in r["title"]
    assert r["email"] == "jango@ufl.edu"
    assert r["google_scholar"] == "https://scholar.google.com/citations?user=ABC123"
    assert "Nutrient, Pesticide, and Waste Management" in r["research_areas"]
    assert "Wetlands and Aquatic Ecosystems" in r["research_areas"]
    assert any("sustainable agriculture" in a for a in r["research_areas"])
    assert r["edis_url"].startswith("https://edis.ifas.ufl.edu/")


def test_students_table():
    rows = P.parse_students(P.make_soup(STUDENTS), "https://soils.ifas.ufl.edu/people/graduate-students/")
    assert len(rows) == 4
    assert rows[0]["name"] == "Maria Alvarez" and rows[0]["program"] == "MS"
    assert rows[2]["program"] == "PhD" and rows[2]["advisor_raw"] == "Bhadha & Smidt"
    assert "email" not in rows[0]
    assert P.split_advisors("Bhadha & Smidt") == ["Bhadha", "Smidt"]
    assert P.split_advisors("Daroub (Temp)") == ["Daroub"]
    assert P.split_advisors("Kadyampakeni amp; Nunes") == ["Kadyampakeni", "Nunes"]


def test_nav_links():
    cats = P.categorize_links(P.make_soup(IFAS_LIST), "https://soils.ifas.ufl.edu/")
    assert "https://soils.ifas.ufl.edu/people/graduate-students/" in cats["students"]
    assert "https://soils.ifas.ufl.edu/people/" in cats["hub"]


def test_student_lines_in_profile():
    html = """<main><h1>Dr. Jane Smith</h1><p>Professor</p><h3>Lab Members</h3><ul><li>Alex Rivera (PhD)</li><li>Sam Lee, MS</li></ul></main>"""
    r = P.parse_profile(P.make_soup(html), "https://x.ufl.edu/faculty/jane-smith/")
    assert [s["name"] for s in r["profile_students"]] == ["Alex Rivera", "Sam Lee"]
    assert r["profile_students"][0]["program"] == "PhD"


def test_catalog_units_and_site():
    html = """<main><h2>College of Agricultural and Life Sciences</h2><ul><li><a href="/graduate/colleges-departments/agricultural-life-sciences/agronomy/">Agronomy</a></li></ul>
    <h2>College of Dentistry</h2><ul><li><a href="/graduate/colleges-departments/dentistry/dentistry/">Dentistry</a></li></ul><h2>Note</h2><ul><li><a href="/x">no</a></li></ul></main>"""
    units = P.parse_catalog_units(html, "https://gradcatalog.ufl.edu/graduate/colleges-departments/")
    assert [(u["college"], u["name"]) for u in units] == [
        ("College of Agricultural and Life Sciences", "Agronomy"), ("College of Dentistry", "Dentistry")]
    site = P.parse_unit_website('<main><a href="https://agronomy.ifas.ufl.edu/">https://agronomy.ifas.ufl.edu/</a><a href="https://campusmap.ufl.edu/">Map</a></main>', "https://gradcatalog.ufl.edu/x/")
    assert site == "https://agronomy.ifas.ufl.edu/"
