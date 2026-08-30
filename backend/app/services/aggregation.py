"""Real multi-source job aggregation — ported from the Job Engine n8n spec.

Six sources feed one table, each wrapped in its own try/except so a dead or
rate-limited source never takes down the run (Job Engine's own hard-earned
lesson). Two things are deliberately different from the original n8n design:

1. Lane inference is broadened past a single RevOps/GTM persona — an
   unmatched job now falls into `other` instead of being dropped, because a
   general marketplace can't discard most of its own supply.
2. Geo eligibility is a generic `is_remote` / `restricted_to` pair instead
   of a single hardcoded "is this Nigeria-eligible" check — the per-user
   home-market boost is applied later, in the matching service.
"""

import logging
import re
from datetime import datetime, timezone
from xml.etree import ElementTree

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import ExperienceLevel, JobLane, JobStatus, JobType
from app.models.ingestion_run import IngestionRun
from app.models.job import Job

logger = logging.getLogger(__name__)
settings = get_settings()

HTTP_TIMEOUT = 15.0
USER_AGENT = "HuntOpsBot/1.0 (+https://github.com/lilyfrancis/huntops)"

_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    return _TAG_RE.sub(" ", text).replace("&amp;", "&").replace("&nbsp;", " ").strip()


# ---------- source fetchers — each returns a list of raw dicts, source-specific shape ----------

def fetch_remotive() -> list[dict]:
    resp = httpx.get(
        "https://remotive.com/api/remote-jobs",
        params={"limit": 200},
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("jobs", [])


def fetch_remoteok() -> list[dict]:
    resp = httpx.get("https://remoteok.com/api", headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    # First element is a metadata/legal notice row, not a job.
    return data[1:] if isinstance(data, list) and len(data) > 1 else []


_GERMAN_STOPWORDS = re.compile(r"\b(und|der|die|für|mit|wir|suchen|aufgaben|m/w/d)\b", re.I)
_INTERN_PATTERN = re.compile(r"\b(praktik|werkstudent|intern|ausbildung|minijob|working student)\b", re.I)


def fetch_arbeitnow() -> list[dict]:
    resp = httpx.get("https://www.arbeitnow.com/api/job-board-api", headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    jobs = resp.json().get("data", [])

    filtered = []
    for job in jobs:
        text = f"{job.get('title', '')} {job.get('description', '')}"
        german_hits = len(_GERMAN_STOPWORDS.findall(text))
        if german_hits >= 3 or _INTERN_PATTERN.search(text):
            continue
        filtered.append(job)
    return filtered


def fetch_jobicy() -> list[dict]:
    resp = httpx.get(
        "https://jobicy.com/api/v2/remote-jobs",
        params={"count": 100},
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("jobs", [])


_WWR_FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-sales-and-marketing-jobs.rss",
    "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss",
]


def fetch_weworkremotely() -> list[dict]:
    jobs = []
    for feed_url in _WWR_FEEDS:
        resp = httpx.get(feed_url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.content)
        for item in root.findall(".//item"):
            title_raw = (item.findtext("title") or "").strip()
            company, _, role = title_raw.partition(": ")
            jobs.append(
                {
                    "company": company or "Unknown",
                    "title": role or title_raw,
                    "url": (item.findtext("link") or "").strip(),
                    "description": item.findtext("description") or "",
                }
            )
    return jobs


def fetch_adzuna() -> list[dict]:
    if not (settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY):
        logger.info("Adzuna skipped — ADZUNA_APP_ID/ADZUNA_APP_KEY not configured")
        return []

    jobs = []
    for country in ("gb", "us"):  # Adzuna has no Nigeria/emerging-market index
        resp = httpx.get(
            f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
            params={
                "app_id": settings.ADZUNA_APP_ID,
                "app_key": settings.ADZUNA_APP_KEY,
                "results_per_page": 20,
            },
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        for item in resp.json().get("results", []):
            item["_country"] = country
            jobs.append(item)
    return jobs


SOURCES = {
    "remotive": fetch_remotive,
    "remoteok": fetch_remoteok,
    "arbeitnow": fetch_arbeitnow,
    "jobicy": fetch_jobicy,
    "weworkremotely": fetch_weworkremotely,
    "adzuna": fetch_adzuna,
}


# ---------- lane inference — broadened past Job Engine's single-persona taxonomy ----------

_LANE_PATTERNS: list[tuple[JobLane, re.Pattern]] = [
    (JobLane.leadership, re.compile(
        r"\b(general manager|chief operating|\bcoo\b|chief revenue|\bcro\b|chief business|\bcbdo\b|"
        r"chief commercial|head of growth|head of revenue|vp of|managing director|chief executive|"
        r"\bceo\b|chief technology|\bcto\b)\b", re.I)),
    (JobLane.engineering, re.compile(
        r"\b(software engineer|developer|programmer|backend|front[- ]end|full[- ]stack|devops|\bsre\b|"
        r"site reliability|data engineer|qa engineer|mobile engineer|ios developer|android developer)\b", re.I)),
    (JobLane.product, re.compile(r"\b(product manager|product owner|product lead|product analyst)\b", re.I)),
    (JobLane.design, re.compile(r"\b(product designer|ux designer|ui designer|graphic designer|visual designer|design lead)\b", re.I)),
    (JobLane.revops, re.compile(r"\b(revops|revenue operations|sales operations|marketing operations)\b", re.I)),
    (JobLane.gtm, re.compile(r"\b(go[- ]to[- ]market|\bgtm\b|revenue engineer|growth engineer)\b", re.I)),
    (JobLane.automation, re.compile(
        r"\b(automation engineer|automation specialist|workflow automation|marketing automation|"
        r"no[- ]code|integration engineer|integration specialist|solutions engineer|n8n|zapier)\b", re.I)),
    (JobLane.sales, re.compile(r"\b(account executive|sales rep|sales representative|business development|\bbdr\b|\bsdr\b|partnership manager)\b", re.I)),
    (JobLane.customer_success, re.compile(r"\b(customer success|customer support|support specialist|client success)\b", re.I)),
    (JobLane.marketing, re.compile(r"\b(marketing|demand gen|growth marketing|performance marketing|lifecycle marketing|\bseo\b|brand manager|content marketing)\b", re.I)),
    (JobLane.operations, re.compile(r"\b(operations manager|ops manager|business operations|operations lead|office manager)\b", re.I)),
    (JobLane.finance, re.compile(r"\b(finance manager|financial analyst|controller|accountant|accounting)\b", re.I)),
    (JobLane.hr, re.compile(r"\b(human resources|hr manager|people operations|talent acquisition|recruiter|recruiting)\b", re.I)),
]


def infer_lane(title: str, description: str) -> JobLane:
    text = f"{title} {description}"
    for lane, pattern in _LANE_PATTERNS:
        if pattern.search(text):
            return lane
    return JobLane.other


_SENIOR_PATTERN = re.compile(r"\b(senior|sr\.?|lead|principal|staff)\b", re.I)
_ENTRY_PATTERN = re.compile(r"\b(junior|jr\.?|entry[- ]level|graduate|intern)\b", re.I)


def infer_experience_level(title: str) -> ExperienceLevel:
    if _SENIOR_PATTERN.search(title):
        return ExperienceLevel.senior
    if _ENTRY_PATTERN.search(title):
        return ExperienceLevel.entry
    return ExperienceLevel.mid


_CONTRACT_PATTERN = re.compile(r"\bcontract\b", re.I)
_PART_TIME_PATTERN = re.compile(r"\bpart[- ]time\b", re.I)
_INTERNSHIP_PATTERN = re.compile(r"\bintern(ship)?\b", re.I)


def infer_job_type(title: str, description: str) -> JobType:
    text = f"{title} {description}"
    if _INTERNSHIP_PATTERN.search(text):
        return JobType.internship
    if _CONTRACT_PATTERN.search(text):
        return JobType.contract
    if _PART_TIME_PATTERN.search(text):
        return JobType.part_time
    return JobType.full_time


# ---------- geo heuristics — generic restriction detection, not one hardcoded country ----------

_REMOTE_PATTERN = re.compile(r"\b(remote|worldwide|anywhere|global)\b", re.I)
_RESTRICTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(us[- ]?only|united states only|us[- ]?based|us citizens? only|must be based in the us)\b", re.I), "US"),
    (re.compile(r"\b(uk[- ]?only|united kingdom only|uk[- ]?based)\b", re.I), "UK"),
    (re.compile(r"\b(eu[- ]?only|european union only|eu[- ]?based)\b", re.I), "EU"),
]


def infer_is_remote(location: str) -> bool:
    return bool(_REMOTE_PATTERN.search(location or ""))


def infer_restriction(location: str, description: str) -> str | None:
    text = f"{location} {description}"
    for pattern, code in _RESTRICTION_PATTERNS:
        if pattern.search(text):
            return code
    return None


# ---------- normalization — one source-specific mapper each, into the Job column shape ----------

def normalize_common(
    *, title: str, company: str | None, url: str, location: str, description: str,
    requirements: list[str], salary_range: str | None, source: str,
) -> dict | None:
    title = (title or "").strip()
    url = (url or "").strip()
    if not title or not url:
        return None

    clean_description = strip_html(description)[:4000]
    return {
        "title": title[:255],
        "company_name": (company or None),
        "employer_id": None,
        "employer_name": None,
        "description": clean_description or "No description provided.",
        "requirements": requirements[:15],
        "location": (location or "Not specified")[:255],
        "salary_range": salary_range,
        "job_type": infer_job_type(title, clean_description),
        "experience_level": infer_experience_level(title),
        "status": JobStatus.active,  # aggregated jobs skip the internal approval queue
        "is_featured": False,
        "source": source,
        "source_url": url,
        "lane": infer_lane(title, clean_description),
        "is_remote": infer_is_remote(location),
        "restricted_to": infer_restriction(location, clean_description),
    }


def normalize_remotive(raw: dict) -> dict | None:
    return normalize_common(
        title=raw.get("title", ""),
        company=raw.get("company_name"),
        url=raw.get("url", ""),
        location=raw.get("candidate_required_location", ""),
        description=raw.get("description", ""),
        requirements=raw.get("tags", []) or [],
        salary_range=raw.get("salary") or None,
        source="remotive",
    )


def normalize_remoteok(raw: dict) -> dict | None:
    salary_min, salary_max = raw.get("salary_min"), raw.get("salary_max")
    salary_range = f"${salary_min:,}–${salary_max:,}" if salary_min and salary_max else None
    return normalize_common(
        title=raw.get("position", ""),
        company=raw.get("company"),
        url=raw.get("url", ""),
        location=raw.get("location", "Remote"),
        description=raw.get("description", ""),
        requirements=raw.get("tags", []) or [],
        salary_range=salary_range,
        source="remoteok",
    )


def normalize_arbeitnow(raw: dict) -> dict | None:
    job_types = raw.get("job_types", []) or []
    location = "Remote" if raw.get("remote") else (raw.get("location") or "Not specified")
    return normalize_common(
        title=raw.get("title", ""),
        company=raw.get("company_name"),
        url=raw.get("url", ""),
        location=location,
        description=raw.get("description", ""),
        requirements=(raw.get("tags", []) or []) + job_types,
        salary_range=None,
        source="arbeitnow",
    )


def normalize_jobicy(raw: dict) -> dict | None:
    industries = raw.get("jobIndustry", []) or []
    salary_min, salary_max = raw.get("annualSalaryMin"), raw.get("annualSalaryMax")
    salary_range = f"${salary_min:,}–${salary_max:,}" if salary_min and salary_max else None
    return normalize_common(
        title=raw.get("jobTitle", ""),
        company=raw.get("companyName"),
        url=raw.get("url", ""),
        location=raw.get("jobGeo", "Remote"),
        description=raw.get("jobExcerpt") or raw.get("jobDescription") or "",
        requirements=industries if isinstance(industries, list) else [str(industries)],
        salary_range=salary_range,
        source="jobicy",
    )


def normalize_weworkremotely(raw: dict) -> dict | None:
    return normalize_common(
        title=raw.get("title", ""),
        company=raw.get("company"),
        url=raw.get("url", ""),
        location="Remote",
        description=raw.get("description", ""),
        requirements=[],
        salary_range=None,
        source="weworkremotely",
    )


def normalize_adzuna(raw: dict) -> dict | None:
    location = raw.get("location", {}).get("display_name", "") if isinstance(raw.get("location"), dict) else ""
    salary_min, salary_max = raw.get("salary_min"), raw.get("salary_max")
    salary_range = f"£{salary_min:,.0f}–£{salary_max:,.0f}" if salary_min and salary_max else None
    return normalize_common(
        title=raw.get("title", ""),
        company=(raw.get("company") or {}).get("display_name"),
        url=raw.get("redirect_url", ""),
        location=location,
        description=raw.get("description", ""),
        requirements=[],
        salary_range=salary_range,
        source=f"adzuna-{raw.get('_country', '')}",
    )


NORMALIZERS = {
    "remotive": normalize_remotive,
    "remoteok": normalize_remoteok,
    "arbeitnow": normalize_arbeitnow,
    "jobicy": normalize_jobicy,
    "weworkremotely": normalize_weworkremotely,
    "adzuna": normalize_adzuna,
}


# ---------- orchestrator ----------

def ingest_all(db: Session, daily_cap: int | None = None) -> dict:
    """Fetch every source, normalize, dedupe by source_url, and persist.

    Each source gets its own IngestionRun row regardless of outcome, so a
    failing or rate-limited source is visible to admins instead of silently
    shrinking the feed.
    """
    remaining_cap = daily_cap if daily_cap is not None else settings.AGGREGATION_DAILY_CAP
    seen_urls_this_run: set[str] = set()
    summary: dict[str, dict] = {}

    for source_name, fetch_fn in SOURCES.items():
        started_at = datetime.now(timezone.utc)
        status, error, fetched, inserted = "success", None, 0, 0

        try:
            raw_jobs = fetch_fn()
            fetched = len(raw_jobs)
            normalizer = NORMALIZERS[source_name]

            for raw in raw_jobs:
                if remaining_cap <= 0:
                    break

                normalized = normalizer(raw)
                if not normalized:
                    continue

                url = normalized["source_url"]
                if url in seen_urls_this_run:
                    continue
                if db.query(Job.id).filter(Job.source_url == url).first():
                    seen_urls_this_run.add(url)
                    continue

                db.add(Job(**normalized))
                seen_urls_this_run.add(url)
                inserted += 1
                remaining_cap -= 1
        except Exception as e:  # one dead source must never kill the whole run
            status, error = "error", str(e)[:2000]
            logger.error("Aggregation source '%s' failed: %s", source_name, e)

        db.add(IngestionRun(
            source=source_name, status=status, fetched_count=fetched, inserted_count=inserted,
            error=error, started_at=started_at, finished_at=datetime.now(timezone.utc),
        ))
        summary[source_name] = {"fetched": fetched, "inserted": inserted, "status": status}

    db.commit()
    return summary
