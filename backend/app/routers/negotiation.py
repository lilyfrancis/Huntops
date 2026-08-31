import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.core.security import require_job_seeker
from app.db.base import get_db
from app.models.negotiation import NegotiationReview
from app.models.user import User
from app.schemas.negotiation import CurrencyCoverage, NegotiationRequest, NegotiationReviewOut
from app.services import benchmarks
from app.services import negotiation as negotiation_service
from app.services.ai_client import AIResponseError

router = APIRouter(prefix="/api/negotiation", tags=["negotiation"])


@router.post("", response_model=NegotiationReviewOut, status_code=201)
@limiter.limit("10/hour")
def review_offer(
    request: Request,
    payload: NegotiationRequest,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> NegotiationReview:
    try:
        return negotiation_service.review_offer(
            db,
            current_user,
            role_title=payload.role_title,
            company_name=payload.company_name,
            location=payload.location,
            currency=payload.currency,
            base_salary=payload.base_salary,
            equity=payload.equity,
            other_terms=payload.other_terms,
            has_competing_offer=payload.has_competing_offer,
            lane=payload.lane,
            experience_level=payload.experience_level,
        )
    except negotiation_service.TierRequiredError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except negotiation_service.InsufficientCreditsError as e:
        raise HTTPException(status_code=402, detail=str(e))
    except AIResponseError as e:
        raise HTTPException(status_code=502, detail=f"Coaching this offer failed: {e}")


@router.get("", response_model=list[NegotiationReviewOut])
def list_my_reviews(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> list[NegotiationReview]:
    return (
        db.query(NegotiationReview)
        .filter(NegotiationReview.user_id == current_user.id)
        .order_by(desc(NegotiationReview.created_at))
        .all()
    )


@router.get("/coverage", response_model=list[CurrencyCoverage])
def salary_data_coverage(
    _: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> list[dict]:
    """How many parsed listings we hold per currency.

    Surfaced so the UI can set expectations before someone fills in the form —
    a market we hold no data for will get tactics-only advice.
    """
    return benchmarks.currency_coverage(db)


@router.get("/{review_id}", response_model=NegotiationReviewOut)
def get_review(
    review_id: uuid.UUID,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> NegotiationReview:
    review = db.get(NegotiationReview, review_id)
    if not review or review.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Review not found")
    return review
