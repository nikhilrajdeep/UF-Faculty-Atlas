import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from atlas.clean import finalize  # noqa: E402

UNITS = [{"name": "Soil, Water, and Ecosystem Sciences", "college": "College of Agricultural and Life Sciences"}]


def rec(name, **kw):
    base = {"id": "", "name": name, "title": "Professor", "college": "", "department": "", "affiliations": [], "email": "",
            "research_areas": [], "research_summary": "", "teaching": [], "extension": [], "google_scholar": "", "roles": [],
            "location": "", "lab_name": ""}
    base.update(kw)
    return base


def test_page_furniture_removed_from_research_and_teaching():
    r = rec("Kimberly Stubbs", department="Soil, Water, and Ecosystem Sciences", college="College of Agricultural and Life Sciences",
            research_areas=["Dr.", "Kimberly", "Department:", "Email:", "PHHP-COM BIOSTATISTICS", "Ph.D.", "Soil Physics", "Stubbs, Kimberly", "Soil Physics"],
            teaching=["Course Title | Frequency", "Manage consent Manage consent", "SWS3022L – Introduction to Soils Lab",
                      "Mailing Address: Fifield Hall 2550 Hull Road"])
    out = finalize([r], UNITS)[0]
    assert out["research_areas"] == ["Soil Physics"]
    assert out["teaching"] == ["SWS3022L – Introduction to Soils Lab"]


def test_shared_department_email_is_kept_only_for_matching_person():
    a, b, c = (rec("Ann Smith", email="office@ufl.edu"), rec("Bob Jones", email="office@ufl.edu"), rec("Cy Lee", email="clee@ufl.edu"))
    out = finalize([a, b, c], UNITS)
    assert [r["email"] for r in out] == ["", "", "clee@ufl.edu"]
    a, b = rec("Ann Smith", email="asmith@ufl.edu"), rec("Bob Jones", email="asmith@ufl.edu")
    assert [r["email"] for r in finalize([a, b], UNITS)] == ["asmith@ufl.edu", ""]


def test_college_inferred_for_catalog_only_labels_and_entities_fixed():
    r = rec("Jo Park", department="Sociology and Criminology &amp; Law")
    out = finalize([r], UNITS)[0]
    assert out["department"] == "Sociology and Criminology & Law"
    assert out["college"] == "College of Liberal Arts and Sciences"


def test_staff_without_faculty_signals_dropped_but_faculty_directors_kept():
    staff = rec("Lane Blanchard", title="Campus IT Director")
    prof = rec("Pat Kay", title="Professor and Director of Graduate Studies")
    names = [r["name"] for r in finalize([staff, prof], UNITS)]
    assert names == ["Pat Kay"]


def test_same_person_listed_by_several_departments_is_one_record():
    shared = lambda d: {"college": "College of Public Health and Health Professions", "department": d, "shared": True}  # noqa: E731
    recs = [rec("Dahomey Abanishe", email="dabanishe@ufl.edu", department=d, affiliations=[shared(d)]) for d in
            ("Biostatistics", "Epidemiology", "Speech, Language, and Hearing Sciences")]
    recs[1]["_cat_dept"] = "Epidemiology"
    out = finalize(recs, UNITS)
    assert len(out) == 1
    assert out[0]["department"] == "Epidemiology"
    assert [a["department"] for a in out[0]["affiliations"]] == ["Epidemiology"]


def test_college_wide_list_without_catalog_match_keeps_college_only():
    shared = {"college": "College of Medicine", "department": "Anatomy", "shared": True}
    out = finalize([rec("Pat Kay", affiliations=[shared], department="Anatomy")], UNITS)
    assert out[0]["department"] == "" and out[0]["college"] == "College of Medicine"


def test_unit_names_are_not_research_areas_and_namesakes_stay_separate():
    r = rec("Jo Park", research_areas=["Soil, Water, and Ecosystem Sciences", "Wetland ecology", "CLIN AST PROF"])
    assert finalize([r], UNITS)[0]["research_areas"] == ["Wetland ecology"]
    a, b = rec("Wei Zhang", email="wz1@ufl.edu", profile_url="https://a.ufl.edu/1"), rec("Wei Zhang", email="wz2@ufl.edu", profile_url="https://b.ufl.edu/2")
    assert len(finalize([a, b], UNITS)) == 2


def test_student_junk_rejected():
    from atlas.clean import student_name_ok
    for bad in ("TRM Professional Paper Syllabus", "Financial Assistance", "Dickinson Hall", "SPM Special Course Registration Form",
                "Beekeeping Certificate- Unique Credit Form"):
        assert not student_name_ok(bad), bad
    assert student_name_ok("Jayani Melanika Madhuhansi Wilegoda Mudalige") and student_name_ok("Arielle Marshall")


def test_bare_catalog_row_merges_into_the_crawled_profile():
    full = rec("Monika Ardelt", email="ardelt@ufl.edu", research_areas=["Aging"], profile_url="https://x.ufl.edu/ardelt/",
               department="Sociology", affiliations=[{"college": "CLAS", "department": "Sociology"}])
    row = rec("Monika Ardelt", department="Sociology and Criminology & Law", affiliations=[])
    out = finalize([row, full], UNITS)
    assert len(out) == 1 and out[0]["email"] == "ardelt@ufl.edu" and out[0]["research_areas"] == ["Aging"]


def test_more_noise_rules():
    from atlas.clean import student_name_ok
    r = rec("Jo Park", research_areas=["M.S.: University of Florida, Animal Sciences", "Ph.D.: AMCB Student", "Professor of Law", "Home Page",
                                       "ecology", "Machine Learning"])
    assert finalize([r], UNITS)[0]["research_areas"] == ["ecology", "Machine Learning"]
    assert finalize([rec("Schedule Consultation"), rec("Pat Kay")], UNITS)[0]["name"] == "Pat Kay"
    assert not student_name_ok("Dr. Jules Bruck This July") and student_name_ok("Will Smith")
    a = rec("Jessica Allen", email="jessal@ufl.edu", research_areas=["Biomechanics"])
    b = rec("Jessica Allen", research_areas=["Biomechanics", "Rehabilitation"], profile_url="https://x.ufl.edu/a")
    assert len(finalize([a, b], UNITS)) == 1


def test_courses_in_research_move_to_teaching_and_titles_trimmed():
    r = rec("Ebrahim Babaeian", research_areas=["Teaching SWS 4602C/5605C Environmental Soil Physics", "Soil physics"],
            title="Associate Professor, Soil, Water & Nutrient Management Everglades Research and Education Center Jehangir Bhadha's EREC Profile Page")
    out = finalize([r], UNITS)[0]
    assert out["research_areas"] == ["Soil physics"]
    assert out["teaching"] == ["SWS 4602C/5605C Environmental Soil Physics"]
    assert out["title"].endswith("Education Center")
