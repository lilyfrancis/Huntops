import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.enums import SubscriptionTier, UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole
    company_name: str | None = None

    @field_validator("role")
    @classmethod
    def role_must_be_self_registerable(cls, v: UserRole) -> UserRole:
        if v == UserRole.admin:
            raise ValueError("Admin accounts cannot be self-registered")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    company_name: str | None
    home_market: str | None
    subscription_tier: SubscriptionTier
    ai_credits: int
    is_approved: bool
    created_at: datetime


class UserProfileUpdate(BaseModel):
    full_name: str | None = None
    company_name: str | None = None
    home_market: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
