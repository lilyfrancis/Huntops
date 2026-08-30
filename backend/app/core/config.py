import logging
import sys
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql+psycopg://huntops:huntops@localhost:5432/huntops"

    # Auth
    JWT_SECRET: str = "dev-only-change-me-before-deploying-1234567890"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # CORS
    CORS_ORIGINS: str = "*"

    # Feature flags
    ENABLE_SIGNUP: bool = True
    AUTO_APPROVE_EMPLOYERS: bool = False
    AUTO_APPROVE_JOBS: bool = False

    # Credits per tier (granted on signup / renewal)
    FREE_TIER_CREDITS: int = 10
    PRO_TIER_CREDITS: int = 100
    ELITE_TIER_CREDITS: int = 500

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_PRO: str = ""
    STRIPE_PRICE_ELITE: str = ""
    FRONTEND_URL: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_settings_on_startup(settings: Settings) -> None:
    """Fail fast on missing config, warn loudly on unsafe defaults.

    Mirrors the one thing the prior prototype (JobQuick) got right: printing
    these warnings at boot instead of only documenting them in a deploy guide.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if settings.ENVIRONMENT == "production":
        if "change-me" in settings.JWT_SECRET or len(settings.JWT_SECRET) < 32:
            errors.append("JWT_SECRET must be a strong random value (32+ chars) in production")
        if settings.CORS_ORIGINS == "*":
            warnings.append("CORS_ORIGINS is '*' — restrict to real origins before launch")
        if not settings.STRIPE_SECRET_KEY:
            warnings.append("STRIPE_SECRET_KEY is unset — billing endpoints will fail")
        if not settings.STRIPE_WEBHOOK_SECRET:
            warnings.append("STRIPE_WEBHOOK_SECRET is unset — webhook signature checks will fail")

    if errors:
        for e in errors:
            logger.error("Config error: %s", e)
        print("\n".join(f"CONFIG ERROR: {e}" for e in errors), file=sys.stderr)
        raise SystemExit(1)

    for w in warnings:
        logger.warning("Config warning: %s", w)
        print(f"WARNING: {w}", file=sys.stderr)
