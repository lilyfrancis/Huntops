"""Salary benchmarks computed from our own aggregated listings.

The corpus is the jobs we already ingest from six sources. That makes the
benchmark first-party and explainable — we can always say exactly how many
listings a figure came from and over what window — instead of a number the
model remembered from training.

Three rules make it honest, and they are the point of this module:

1. **Never mix currencies.** We have no FX source, and converting at a made-up
   rate would silently corrupt every cross-market comparison.
2. **Never quote below a minimum sample.** A "median" over three listings is
   noise wearing a statistic's clothes.
3. **Always report n and the window.** A caller that can't say where a number
   came from shouldn't be showing it.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.enums import ExperienceLevel, JobLane, JobStatus
from app.models.job import Job

MIN_SAMPLE = 10
LOOKBACK_DAYS = 180


def _percentile(sorted_values: list[float], fraction: float) -> float:
    """Linear-interpolated percentile. Small samples make numpy overkill here."""
    if not sorted_values:
        raise ValueError("no values")
    if len(sorted_values) == 1:
        return sorted_values[0]

    position = fraction * (len(sorted_values) - 1)
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    weight = position - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


def benchmark(
    db: Session,
    *,
    lane: JobLane | None,
    currency: str,
    experience_level: ExperienceLevel | None = None,
    is_remote: bool | None = None,
) -> dict | None:
    """Return salary percentiles for a cohort, or None if the sample is too thin.

    Cohort is (lane, currency) — plus experience level and remote status when
    given. Matching on lane rather than raw job title is deliberate: titles are
    unstandardized across sources ("Sr. RevOps Mgr" vs "Senior Revenue
    Operations Manager"), while lane is already inferred consistently at ingest.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    query = db.query(Job).filter(
        Job.status == JobStatus.active,
        Job.salary_currency == currency,
        Job.salary_annual_min.isnot(None),
        Job.created_at >= cutoff,
    )
    if lane is not None:
        query = query.filter(Job.lane == lane)
    if experience_level is not None:
        query = query.filter(Job.experience_level == experience_level)
    if is_remote is not None:
        query = query.filter(Job.is_remote.is_(is_remote))

    jobs = query.all()

    # Use each listing's midpoint: a posted band's middle is the closest single
    # number to what the role is actually advertised at.
    midpoints = sorted(
        ((job.salary_annual_min + (job.salary_annual_max or job.salary_annual_min)) / 2)
        for job in jobs
    )

    if len(midpoints) < MIN_SAMPLE:
        return None

    return {
        "currency": currency,
        "sample_size": len(midpoints),
        "lookback_days": LOOKBACK_DAYS,
        "p25": round(_percentile(midpoints, 0.25)),
        "median": round(_percentile(midpoints, 0.50)),
        "p75": round(_percentile(midpoints, 0.75)),
        "lane": lane.value if lane else None,
        "experience_level": experience_level.value if experience_level else None,
    }


def benchmark_for_offer(
    db: Session,
    *,
    lane: JobLane | None,
    currency: str,
    experience_level: ExperienceLevel | None,
) -> dict | None:
    """Best available benchmark, widening the cohort rather than going silent.

    Tries the tightest cohort first and drops constraints one at a time. A
    broader benchmark with an honest label beats no benchmark at all — but the
    result always says which cohort it actually used.
    """
    attempts = [
        {"lane": lane, "experience_level": experience_level},
        {"lane": lane, "experience_level": None},
        {"lane": None, "experience_level": None},
    ]
    for attempt in attempts:
        result = benchmark(db, currency=currency, **attempt)
        if result is not None:
            result["cohort"] = (
                "lane and experience level"
                if attempt["experience_level"]
                else "lane" if attempt["lane"]
                else "all roles in this currency"
            )
            return result
    return None


def currency_coverage(db: Session) -> list[dict]:
    """How much parsed salary data we hold per currency — powers the honesty note."""
    rows = (
        db.query(Job.salary_currency, func.count(Job.id))
        .filter(Job.salary_currency.isnot(None), Job.salary_annual_min.isnot(None))
        .group_by(Job.salary_currency)
        .all()
    )
    return sorted(
        [{"currency": currency, "listings": count} for currency, count in rows],
        key=lambda row: row["listings"],
        reverse=True,
    )
