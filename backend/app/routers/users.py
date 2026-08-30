from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import UserOut, UserProfileUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.put("/profile", response_model=UserOut)
def update_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.company_name is not None:
        current_user.company_name = payload.company_name
    if payload.home_market is not None:
        current_user.home_market = payload.home_market
    if payload.positioning_statement is not None:
        current_user.positioning_statement = payload.positioning_statement

    db.commit()
    db.refresh(current_user)
    return current_user
