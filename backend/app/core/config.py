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

    # AI (Anthropic) — cheap Haiku tier for scoring/extraction, Sonnet reserved
    # for Phase 4's outreach drafting (higher quality writing, higher cost).
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_SCORING_MODEL: str = "claude-haiku-4-5-20251001"
    ANTHROPIC_DRAFTING_MODEL: str = "claude-sonnet-5"

    # Résumé upload
    MAX_UPLOAD_SIZE_MB: int = 5
    ALLOWED_RESUME_EXTENSIONS: str = ".pdf,.docx,.txt"

    # Job aggregation
    AGGREGATION_DAILY_CAP: int = 200
    MAX_MATCH_CANDIDATES: int = 40
    GEO_MATCH_BOOST: int = 15
    ADZUNA_APP_ID: str = ""
    ADZUNA_APP_KEY: str = ""
    ENABLE_SCHEDULED_AGGREGATION: bool = True

    # Gmail OAuth (email-alert bridge)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/integrations/gmail/callback"
    TOKEN_ENCRYPTION_KEY: str = ""
    GMAIL_LABEL_NAME: str = "HuntOps"
    EMAIL_ALERT_SENDER_DOMAINS: str = "linkedin.com,indeed.com,glassdoor.com,jobberman.com,myjobmag.com,theladders.com"
    ENABLE_SCHEDULED_EMAIL_SYNC: bool = True
    EMAIL_SYNC_QUERY_WINDOW: str = "newer_than:2d"

    # Apollo (recruiter discovery) + outreach drafting — Autopilot Outreach,
    # gated to the elite tier and metered in credits since both an Apollo
    # reveal and a Sonnet-tier draft cost real money per call.
    APOLLO_API_KEY: str = ""
    RECRUITER_TITLES: str = (
        "Recruiter,Technical Recruiter,Talent Acquisition,Talent Partner,"
        "Head of Talent,Head of People,People Operations Manager,HR Manager,"
        "Hiring Manager,Recruitment Manager"
    )
    OUTREACH_CREDIT_COST: int = 30

    # Mock interview: charged once up front for the whole session, so a user
    # is never stranded mid-interview by an empty balance.
    INTERVIEW_CREDIT_COST: int = 15
    INTERVIEW_QUESTION_COUNT: int = 5

    # Negotiation coach: one grounded review per offer.
    NEGOTIATION_CREDIT_COST: int = 20

    @property
    def recruiter_titles_list(self) -> List[str]:
        return [t.strip() for t in self.RECRUITER_TITLES.split(",") if t.strip()]

    # Outbound platform email (digest, admin alerts) — deliberately generic
    # SMTP rather than a vendor SDK, so any provider's SMTP relay works
    # (SendGrid, Postmark, SES, or a real mailbox in dev).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@huntops.app"
    SMTP_USE_TLS: bool = True
    ADMIN_ALERT_EMAIL: str = ""

    ENABLE_SCHEDULED_DIGEST: bool = True
    DIGEST_MAX_JOBS: int = 10

    # For the admin revenue estimate only — not used for actual billing,
    # which is entirely Stripe-driven (see services/billing.py).
    PRO_PRICE_USD: float = 24.0
    ELITE_PRICE_USD: float = 89.0

    @property
    def allowed_resume_extensions_list(self) -> List[str]:
        return [e.strip() for e in self.ALLOWED_RESUME_EXTENSIONS.split(",") if e.strip()]

    @property
    def email_alert_sender_domains_list(self) -> List[str]:
        return [d.strip() for d in self.EMAIL_ALERT_SENDER_DOMAINS.split(",") if d.strip()]

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
