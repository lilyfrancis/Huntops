"""Negotiation coach — offer strategy grounded in our own listing data.

The hard rule this module exists to enforce: **the model never supplies the
number.** A benchmark comes from `benchmarks.py` (percentiles over real
listings) or there is no benchmark, and the prompt is told so explicitly. A
model asked "is £70k low for this role?" will happily answer from memory —
stale, US-skewed, and confidently wrong for Lagos or Nairobi. Someone could
turn down a real offer on the strength of it.

So there are two prompts, not one:
  - with a benchmark: reason against these percentiles, cite them
  - without: tactics and scripting only, and say plainly that we don't know
    the market rate

Available on Pro and Elite, like the interview simulator.
"""

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import ExperienceLevel, JobLane, SubscriptionTier
from app.models.negotiation import NegotiationReview
from app.models.user import User
from app.schemas.ai import NegotiationAdvice, validate_or_raise
from app.services import ai_client, benchmarks
from app.services.aggregation import infer_lane
from app.services.credits import adjust_credits

logger = logging.getLogger(__name__)
settings = get_settings()


class TierRequiredError(Exception):
    pass


class InsufficientCreditsError(Exception):
    pass


SYSTEM_PROMPT = (
    "You are a compensation negotiation coach. You are direct, practical, and never "
    "sycophantic. You write scripts the candidate can actually send. You never invent "
    "salary figures: if you are not given market data, you say plainly that you don't "
    "know the market rate and coach on everything else instead."
)


def _offer_block(role_title: str, company: str | None, location: str, currency: str,
                 base: float, equity: str | None, other: str | None,
                 competing: bool) -> str:
    lines = [
        f"Role: {role_title}",
        f"Company: {company or 'not specified'}",
        f"Location / market: {location}",
        f"Base offered: {base:,.0f} {currency} per year",
        f"Equity or bonus: {equity or 'none mentioned'}",
        f"Other terms the candidate flagged: {other or 'none'}",
        f"Competing offer in hand: {'yes' if competing else 'no'}",
    ]
    return "\n".join(lines)


def _benchmark_block(data: dict, base: float) -> str:
    position = (
        "below the 25th percentile" if base < data["p25"]
        else "between the 25th percentile and the median" if base < data["median"]
        else "between the median and the 75th percentile" if base < data["p75"]
        else "at or above the 75th percentile"
    )
    return f"""MARKET DATA (from {data['sample_size']} real listings in the last {data['lookback_days']} days,
cohort: {data['cohort']}, currency {data['currency']}):
  25th percentile: {data['p25']:,}
  median:          {data['median']:,}
  75th percentile: {data['p75']:,}

The offered base sits {position}.

Use ONLY these figures when you reference market rate. Do not introduce any other
number as market data. Cite the sample size when you cite a figure."""


NO_BENCHMARK_BLOCK = """MARKET DATA: none available.

We do not hold enough comparable listings to state a market rate for this role and
currency. You MUST NOT estimate one, and you must not imply you know what the role
"typically" pays. Say plainly that the market rate is unknown here, suggest the
candidate check a source with real local data, and coach on everything that does not
depend on knowing the number: what else is negotiable, how to ask the employer to
justify the figure, how to get them to move first, and the exact wording to use."""


def _build_prompt(offer_block: str, market_block: str) -> str:
    return f"""Coach this candidate on their offer.

{offer_block}

{market_block}

Give:
1. A verdict — is this worth negotiating, and how hard?
2. The levers ranked by what is realistically winnable here, not just base.
3. A counter-offer script they can send as-is: warm, specific, no grovelling,
   no em dashes, under 180 words.
4. What to say if the employer says no.

Respond ONLY with valid minified JSON:
{{"verdict": "...", "confidence": "high|medium|low", "levers": [{{"lever": "...", "rationale": "..."}}],
  "counter_script": "...", "if_they_say_no": "...", "watch_outs": ["..."]}}"""


def review_offer(
    db: Session,
    user: User,
    *,
    role_title: str,
    company_name: str | None,
    location: str,
    currency: str,
    base_salary: float,
    equity: str | None,
    other_terms: str | None,
    has_competing_offer: bool,
    lane: JobLane | None = None,
    experience_level: ExperienceLevel | None = None,
) -> NegotiationReview:
    if user.subscription_tier == SubscriptionTier.free:
        raise TierRequiredError("The negotiation coach is available on Pro and Elite")
    if user.ai_credits < settings.NEGOTIATION_CREDIT_COST:
        raise InsufficientCreditsError(
            f"Need {settings.NEGOTIATION_CREDIT_COST} credits, have {user.ai_credits}"
        )

    # Fall back to inferring the lane from the role title using the *same*
    # function that labelled the corpus at ingest. Reusing it is the point: a
    # second, subtly different classifier here would silently compare the offer
    # against a cohort assembled by different rules.
    if lane is None:
        lane = infer_lane(role_title, "")

    data = benchmarks.benchmark_for_offer(
        db, lane=lane, currency=currency.upper(), experience_level=experience_level
    )

    prompt = _build_prompt(
        _offer_block(role_title, company_name, location, currency.upper(), base_salary,
                     equity, other_terms, has_competing_offer),
        _benchmark_block(data, base_salary) if data else NO_BENCHMARK_BLOCK,
    )

    raw = ai_client.complete_json(
        system=SYSTEM_PROMPT,
        prompt=prompt,
        model=settings.ANTHROPIC_DRAFTING_MODEL,
        max_tokens=1600,
    )
    advice = validate_or_raise(NegotiationAdvice, raw)

    review = NegotiationReview(
        user_id=user.id,
        role_title=role_title[:255],
        company_name=company_name,
        location=location[:255],
        currency=currency.upper()[:3],
        base_salary=base_salary,
        equity=equity,
        other_terms=other_terms,
        has_competing_offer=has_competing_offer,
        verdict=advice.verdict,
        confidence=advice.confidence,
        levers=[lever.model_dump() for lever in advice.levers],
        counter_script=advice.counter_script,
        if_they_say_no=advice.if_they_say_no,
        watch_outs=advice.watch_outs,
        benchmark=data,
    )
    db.add(review)

    # Charged only after the AI call succeeds, matching the interview simulator.
    adjust_credits(db, user, action="negotiation", amount=-settings.NEGOTIATION_CREDIT_COST)
    db.commit()
    db.refresh(review)
    return review
