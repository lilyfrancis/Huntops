import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    validate_password_strength,
    verify_password,
    TokenType,
)
from app.db.base import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import AccessTokenOut, RefreshRequest, TokenPair, UserCreate, UserLogin, UserOut
from app.services.credits import adjust_credits

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenPair, status_code=201)
@limiter.limit("10/hour")
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)) -> TokenPair:
    if not settings.ENABLE_SIGNUP:
        raise HTTPException(status_code=403, detail="Signups are currently disabled")

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    validate_password_strength(payload.password)

    is_approved = True
    if payload.role == UserRole.employer:
        is_approved = settings.AUTO_APPROVE_EMPLOYERS

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        company_name=payload.company_name if payload.role == UserRole.employer else None,
        is_approved=is_approved,
        ai_credits=0,
    )
    db.add(user)
    db.flush()  # assigns user.id without committing yet

    adjust_credits(db, user, action="signup_bonus", amount=settings.FREE_TIER_CREDITS)

    db.commit()
    db.refresh(user)

    return _issue_tokens(user)


@router.post("/login", response_model=TokenPair)
@limiter.limit("5/minute")
def login(request: Request, payload: UserLogin, db: Session = Depends(get_db)) -> TokenPair:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.is_suspended:
        raise HTTPException(status_code=403, detail="Account suspended")

    return _issue_tokens(user)


@router.post("/refresh", response_model=AccessTokenOut)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> AccessTokenOut:
    token_payload = decode_token(payload.refresh_token, TokenType.refresh)
    try:
        user = db.get(User, uuid.UUID(token_payload["sub"]))
    except (ValueError, TypeError):
        user = None
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.is_suspended:
        raise HTTPException(status_code=403, detail="Account suspended")

    return AccessTokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
