import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.core.security import require_job_seeker
from app.db.base import get_db
from app.models.interview import InterviewSession, InterviewTurn
from app.models.job import Job
from app.models.user import User
from app.schemas.interview import (
    AnswerRequest,
    InterviewSessionOut,
    InterviewSessionSummary,
    InterviewStartRequest,
    InterviewTurnOut,
)
from app.services import interviews as interview_service
from app.services.ai_client import AIResponseError

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


def _owned_session(db: Session, session_id: uuid.UUID, user: User) -> InterviewSession:
    session = db.get(InterviewSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Interview not found")
    return session


@router.post("", response_model=InterviewSessionOut, status_code=201)
@limiter.limit("10/hour")
def start_interview(
    request: Request,
    payload: InterviewStartRequest,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> InterviewSession:
    job = None
    if payload.job_id:
        job = db.get(Job, payload.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

    try:
        return interview_service.start_session(db, current_user, job, payload.role_title)
    except interview_service.TierRequiredError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except interview_service.InsufficientCreditsError as e:
        raise HTTPException(status_code=402, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AIResponseError as e:
        raise HTTPException(status_code=502, detail=f"Generating interview questions failed: {e}")


@router.get("", response_model=list[InterviewSessionSummary])
def list_my_interviews(
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> list[InterviewSession]:
    return (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == current_user.id)
        .order_by(desc(InterviewSession.created_at))
        .all()
    )


@router.get("/{session_id}", response_model=InterviewSessionOut)
def get_interview(
    session_id: uuid.UUID,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> InterviewSession:
    return _owned_session(db, session_id, current_user)


@router.post("/{session_id}/turns/{position}/answer", response_model=InterviewTurnOut)
@limiter.limit("60/hour")
def answer_question(
    request: Request,
    session_id: uuid.UUID,
    position: int,
    payload: AnswerRequest,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> InterviewTurn:
    session = _owned_session(db, session_id, current_user)
    turn = next((t for t in session.turns if t.position == position), None)
    if turn is None:
        raise HTTPException(status_code=404, detail="Question not found")

    try:
        return interview_service.submit_answer(db, session, turn, payload.answer)
    except interview_service.SessionClosedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except AIResponseError as e:
        raise HTTPException(status_code=502, detail=f"Grading your answer failed: {e}")


@router.post("/{session_id}/complete", response_model=InterviewSessionOut)
def complete_interview(
    session_id: uuid.UUID,
    current_user: User = Depends(require_job_seeker),
    db: Session = Depends(get_db),
) -> InterviewSession:
    session = _owned_session(db, session_id, current_user)
    try:
        return interview_service.complete_session(db, session)
    except interview_service.SessionClosedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except AIResponseError as e:
        raise HTTPException(status_code=502, detail=f"Summarising the interview failed: {e}")
