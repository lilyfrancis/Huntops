from unittest.mock import patch

from app.models.enums import ExperienceLevel, JobLane, JobType
from app.models.ingestion_run import IngestionRun
from app.models.job import Job
from app.services import aggregation


def test_infer_lane_prioritizes_leadership_over_generic_terms():
    assert aggregation.infer_lane("VP of Marketing", "") == JobLane.leadership
    assert aggregation.infer_lane("Growth Marketing Manager", "") == JobLane.marketing


def test_infer_lane_falls_through_to_other_instead_of_dropping():
    # Job Engine's original taxonomy would have discarded this entirely.
    assert aggregation.infer_lane("Veterinary Technician", "cares for animals") == JobLane.other


def test_infer_lane_covers_engineering_and_design():
    assert aggregation.infer_lane("Senior Backend Developer", "") == JobLane.engineering
    assert aggregation.infer_lane("Product Designer", "") == JobLane.design


def test_infer_experience_level():
    assert aggregation.infer_experience_level("Senior Software Engineer") == ExperienceLevel.senior
    assert aggregation.infer_experience_level("Junior Developer") == ExperienceLevel.entry
    assert aggregation.infer_experience_level("Software Engineer") == ExperienceLevel.mid


def test_infer_job_type():
    assert aggregation.infer_job_type("Marketing Intern", "") == JobType.internship
    assert aggregation.infer_job_type("Contract Developer", "") == JobType.contract
    assert aggregation.infer_job_type("Part-time Designer", "") == JobType.part_time
    assert aggregation.infer_job_type("Software Engineer", "") == JobType.full_time


def test_infer_is_remote_and_restriction():
    assert aggregation.infer_is_remote("Remote") is True
    assert aggregation.infer_is_remote("Worldwide") is True
    assert aggregation.infer_is_remote("New York, NY") is False

    assert aggregation.infer_restriction("Remote (US Only)", "") == "US"
    assert aggregation.infer_restriction("Remote", "Must be based in the US") == "US"
    assert aggregation.infer_restriction("Remote", "Open to candidates worldwide") is None


def test_arbeitnow_filters_german_and_intern_postings():
    fake_response_data = {
        "data": [
            {"title": "Werkstudent Marketing", "company_name": "A", "url": "https://a.example/1", "description": "wir suchen einen praktikanten"},
            {"title": "Senior Backend Engineer", "company_name": "B", "url": "https://b.example/2", "description": "Join our team building APIs", "remote": True},
        ]
    }
    with patch("app.services.aggregation.httpx.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = fake_response_data
        jobs = aggregation.fetch_arbeitnow()

    assert len(jobs) == 1
    assert jobs[0]["title"] == "Senior Backend Engineer"


def test_remoteok_skips_metadata_row():
    with patch("app.services.aggregation.httpx.get") as mock_get:
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = [
            {"legal": "notice"},
            {"position": "Frontend Engineer", "company": "Acme", "url": "https://remoteok.com/1", "location": "Remote"},
        ]
        jobs = aggregation.fetch_remoteok()

    assert len(jobs) == 1
    assert jobs[0]["position"] == "Frontend Engineer"


def test_normalize_remotive_produces_valid_job_fields():
    raw = {
        "title": "Senior RevOps Manager",
        "company_name": "Acme Corp",
        "url": "https://remotive.com/job/123",
        "candidate_required_location": "Worldwide",
        "description": "<p>Own our RevOps stack</p>",
        "tags": ["Salesforce", "HubSpot"],
        "salary": "$100k-$130k",
    }
    normalized = aggregation.normalize_remotive(raw)

    assert normalized["title"] == "Senior RevOps Manager"
    assert normalized["lane"] == JobLane.revops
    assert normalized["is_remote"] is True
    assert normalized["source"] == "remotive"
    assert normalized["source_url"] == "https://remotive.com/job/123"
    assert "Own our RevOps stack" in normalized["description"]


def test_normalize_rejects_jobs_missing_title_or_url():
    assert aggregation.normalize_remotive({"title": "", "url": "https://x.com/1"}) is None
    assert aggregation.normalize_remotive({"title": "Engineer", "url": ""}) is None


def test_ingest_all_dedupes_and_isolates_source_failures(db_session):
    def working_source():
        return [
            {"title": "Backend Engineer", "company": "Acme", "url": "https://x.example/job1", "location": "Remote"},
            {"title": "Backend Engineer", "company": "Acme", "url": "https://x.example/job1", "location": "Remote"},  # duplicate within batch
        ]

    def failing_source():
        raise RuntimeError("upstream API is down")

    def normalize_ok(raw):
        return aggregation._normalize_common(
            title=raw["title"], company=raw["company"], url=raw["url"], location=raw["location"],
            description="", requirements=[], salary_range=None, source="working",
        )

    with patch.dict(aggregation.SOURCES, {"working": working_source, "broken": failing_source}, clear=True), \
         patch.dict(aggregation.NORMALIZERS, {"working": normalize_ok, "broken": lambda r: r}, clear=True):
        summary = aggregation.ingest_all(db_session)

    assert summary["working"]["status"] == "success"
    assert summary["working"]["fetched"] == 2
    assert summary["working"]["inserted"] == 1  # the in-batch duplicate was skipped

    assert summary["broken"]["status"] == "error"
    assert summary["broken"]["inserted"] == 0

    jobs = db_session.query(Job).filter(Job.source == "working").all()
    assert len(jobs) == 1

    runs = db_session.query(IngestionRun).all()
    assert {r.source for r in runs} == {"working", "broken"}
    broken_run = next(r for r in runs if r.source == "broken")
    assert "upstream API is down" in broken_run.error


def test_ingest_all_skips_jobs_already_in_db(db_session):
    db_session.add(Job(
        title="Existing Job", description="desc", requirements=[], location="Remote",
        job_type=JobType.full_time, experience_level=ExperienceLevel.mid, source="working",
        source_url="https://x.example/existing",
    ))
    db_session.commit()

    def working_source():
        return [{"title": "Existing Job", "company": "Acme", "url": "https://x.example/existing", "location": "Remote"}]

    def normalize_ok(raw):
        return aggregation._normalize_common(
            title=raw["title"], company=raw["company"], url=raw["url"], location=raw["location"],
            description="", requirements=[], salary_range=None, source="working",
        )

    with patch.dict(aggregation.SOURCES, {"working": working_source}, clear=True), \
         patch.dict(aggregation.NORMALIZERS, {"working": normalize_ok}, clear=True):
        summary = aggregation.ingest_all(db_session)

    assert summary["working"]["inserted"] == 0
    assert db_session.query(Job).filter(Job.source_url == "https://x.example/existing").count() == 1
