import logging
import re
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
    # Sized against what the plan is for, not against token cost. A
    # concierge application is 15 credits and costs about a hundred naira of
    # someone's time, so a plan's grant is really "how many applications a
    # month is this". 100 credits was six, which an active job seeker
    # exhausts in a week — and a plan you run out of in week one is a plan
    # people leave.
    FREE_TIER_CREDITS: int = 15        # one application, to see it land
    PRO_TIER_CREDITS: int = 300        # about twenty
    ELITE_TIER_CREDITS: int = 1000     # about sixty-five

    # Paystack. Plan codes come from the Paystack dashboard; the *price* lives
    # on the plan there, never here, so the two can't drift apart.
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_PLAN_PRO: str = ""
    PAYSTACK_PLAN_ELITE: str = ""
    FRONTEND_URL: str = "http://localhost:5173"

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

    # Whether job seekers may connect their own Gmail so outreach sends from
    # their address. Off by default because the OAuth client is an *Internal*
    # Workspace app: only accounts in our own Workspace can consent, so a job
    # seeker with a personal Gmail gets an access-blocked error from Google
    # rather than a working feature. Turning this on requires registering a
    # separate External OAuth client and going through Google verification.
    # With it off, outreach sends via the platform relay with the user's
    # address as Reply-To — which needs no Google access at all.
    ENABLE_USER_GMAIL_CONNECT: bool = False
    # Which senders count as job alerts. A mailbox is the operator's own and
    # carries ordinary post too, so anything not on this list is skipped
    # without costing an AI call — which also means an alert from a board that
    # is missing here is silently ignored. Add per market as you open them;
    # subdomains match automatically (jobalerts.linkedin.com).
    EMAIL_ALERT_SENDER_DOMAINS: str = (
        # Global
        "linkedin.com,indeed.com,glassdoor.com,ziprecruiter.com,theladders.com,"
        # UK
        "reed.co.uk,totaljobs.com,cv-library.co.uk,jobsite.co.uk,adzuna.co.uk,"
        # Canada
        "workopolis.com,jobbank.gc.ca,eluta.ca,jobillico.com,"
        # Gulf / UAE
        "bayt.com,gulftalent.com,naukrigulf.com,dubizzle.com,"
        # Nigeria
        "jobberman.com,myjobmag.com,hotnigerianjobs.com"
    )

    # Addresses on an allowed domain that are never job alerts. Job boards use
    # the same domain to tell an *employer* that someone applied to their
    # posting, or that a sponsored listing renewed — mail that matches the
    # allowlist, costs an AI call, and can be misread as a vacancy. Matched on
    # the full address, case-insensitively.
    EMAIL_ALERT_SENDER_EXCLUDES: str = (
        "employers-noreply@indeed.com,no-reply@indeed.com,"
        "employer@indeed.com,noreply-employer@glassdoor.com,"
        "invitationsr@linkedin.com,messages-noreply@linkedin.com,"
        "notifications-noreply@linkedin.com,updates-noreply@linkedin.com,"
        "noreply@monster.com,employer@monster.com,noreply@dice.com"
    )
    ENABLE_SCHEDULED_EMAIL_SYNC: bool = True
    # How far back a mailbox reads on its very first sync, or after a server
    # renumbers a folder and the stored UID cursor becomes meaningless.
    # Steady-state syncs are UID-incremental and ignore this.
    EMAIL_SYNC_LOOKBACK_DAYS: int = 3

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

    # Tailoring an application: a cover letter plus résumé bullets for one
    # job. Cheaper than outreach because there is no Apollo lookup — the
    # cost is a single drafting call — and it is charged once per job, then
    # cached, so revising and re-reading are free.
    TAILOR_CREDIT_COST: int = 10

    # Asking HuntOps to file an application on an external site. A person
    # does this by hand, so it is priced above the AI features rather than
    # against their token cost. Matched to FREE_TIER_CREDITS on purpose: a
    # new account can do exactly one and see it land, which is the argument
    # for the plan.
    CONCIERGE_CREDIT_COST: int = 15
    # What a non-Elite account gets, ever. Enough to feel what it does and
    # see it land, not enough to run a job hunt on. Credits are charged on
    # top, so this is a ceiling rather than a currency.
    CONCIERGE_FREE_ALLOWANCE: int = 3

    # Seeing one external listing in full: the company, the description, the
    # whole title. Priced well under a concierge apply — this is a look, not
    # a piece of work — but not free, because the company name is the thing
    # that lets someone go around us.
    UNLOCK_CREDIT_COST: int = 5

    # Pay-as-you-go top-ups: "code:credits:price" per pack, in
    # BILLING_CURRENCY. Priced above the per-credit rate a subscription
    # gives, on purpose — the plan should always be the better deal, or
    # there is no reason to be on one. Bigger packs get a discount so the
    # step up is worth taking.
    #
    # Amounts here are charged directly rather than read from a Paystack
    # plan, because these are one-off transactions and Paystack plans are
    # for recurring ones. Keep them in step with whatever you advertise.
    CREDIT_PACKS: str = "starter:100:5000,plus:250:11000,pro:600:24000,bulk:1500:52500"
    # Tell an admin the moment work arrives. The queue only updates when
    # somebody opens it, and a request nobody knows about is a user watching
    # "queued" for a day.
    NOTIFY_ADMIN_ON_CONCIERGE: bool = True
    # How long a request may sit before the backlog is worth chasing. The
    # per-request email can be missed; this one cannot be, because it keeps
    # arriving.
    CONCIERGE_SLA_HOURS: int = 24

    @property
    def credit_packs(self) -> list[dict]:
        """Parsed top-up packs, cheapest first.

        A malformed entry is skipped rather than crashing the app: a typo in
        an env var should cost you one pack on a pricing page, not the whole
        deployment.
        """
        packs = []
        for raw in self.CREDIT_PACKS.split(","):
            parts = [p.strip() for p in raw.split(":")]
            if len(parts) != 3:
                continue
            code, credits, price = parts
            try:
                packs.append({"code": code, "credits": int(credits), "price": float(price)})
            except ValueError:
                continue
        return sorted(packs, key=lambda p: p["credits"])

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
    # Implicit TLS (the whole session encrypted from the first byte) rather
    # than STARTTLS. Left unset it follows the port, which is right for every
    # mainstream provider; set it only for implicit TLS on a nonstandard port.
    SMTP_USE_SSL: bool | None = None
    ADMIN_ALERT_EMAIL: str = ""


    # Whether THIS process owns the cron jobs. Must be true in exactly one
    # process: with multiple uvicorn workers, every worker that has this on
    # runs every scheduled job, so digests and aggregation fire N times.
    RUN_SCHEDULER: bool = True

    # WhatsApp (Meta Cloud API) — an alternative digest channel. Email open
    # rates are poor in these markets; WhatsApp is where people read.
    #
    # A business-initiated message must use a template approved by Meta in
    # advance, so the digest becomes a short nudge with counts plus a link,
    # not the list itself. Create a template with three body parameters:
    #   "Hi {{1}}, you have {{2}} new job matches on HuntOps today. Top one: {{3}}"
    # Meta's own endpoint by default. Several providers resell the Cloud API
    # behind their own host with an identical request shape — pointing this at
    # theirs is enough to use them, no code change. A provider with its own
    # payload format needs an adapter instead.
    WHATSAPP_API_BASE: str = "https://graph.facebook.com"
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    # The WhatsApp Business Account the number belongs to. Optional, and used
    # only to verify the template: without it a wrong template name or
    # language is invisible until the first digest fails at 07:30.
    WHATSAPP_WABA_ID: str = ""
    WHATSAPP_TEMPLATE_NAME: str = "huntops_daily_digest"
    # Meta's language *code*, not the language's name. "English" is the
    # natural thing to type here and it is silently wrong: Meta looks for a
    # translation in a language called English, finds none, and answers 132001
    # at 07:30 where nobody is awake to read it. Validated on startup below.
    WHATSAPP_TEMPLATE_LANGUAGE: str = "en"

    # The business number users message to opt in, E.164 — e.g. "+12268010899".
    # Meta drops marketing templates to people who have never engaged with the
    # business, accepting the send with a 200 and delivering nothing, so a
    # digest to somebody who has not messaged first simply vanishes. This is
    # the number behind the "Connect WhatsApp" link.
    WHATSAPP_BUSINESS_NUMBER: str = ""
    # Echoed back to Meta when it verifies the webhook URL. Any string; it
    # must match what is typed into the Meta console.
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = ""
    # Meta signs webhook bodies with the *app* secret. Without it the webhook
    # refuses everything rather than trusting an unsigned caller.
    WHATSAPP_APP_SECRET: str = ""

    ENABLE_SCHEDULED_DIGEST: bool = True

    # Autopilot acts in users' names without asking, so it is opt-in per user
    # (UserPreference) *and* killable platform-wide from here.
    ENABLE_SCHEDULED_AUTOPILOT: bool = True
    DIGEST_MAX_JOBS: int = 10

    # For the admin revenue estimate only — not used for actual billing, which
    # is entirely Paystack-driven (see services/billing.py). Kept in sync with
    # the Paystack plans by hand; the currency is named so the dashboard can't
    # quietly report naira totals under a dollar sign.
    BILLING_CURRENCY: str = "USD"
    PRO_PRICE: float = 24.0
    ELITE_PRICE: float = 89.0

    @property
    def smtp_implicit_tls(self) -> bool:
        """465 is the submissions port and speaks TLS immediately; 587 greets
        in plain text and upgrades with STARTTLS. Getting this backwards does
        not fail cleanly — it hangs until the timeout, which reads like a
        firewall problem and sends you hunting in the wrong place."""
        if self.SMTP_USE_SSL is not None:
            return self.SMTP_USE_SSL
        return self.SMTP_PORT == 465

    @property
    def allowed_resume_extensions_list(self) -> List[str]:
        return [e.strip() for e in self.ALLOWED_RESUME_EXTENSIONS.split(",") if e.strip()]

    @property
    def email_alert_sender_domains_list(self) -> List[str]:
        return [d.strip() for d in self.EMAIL_ALERT_SENDER_DOMAINS.split(",") if d.strip()]

    @property
    def email_alert_sender_excludes_list(self) -> List[str]:
        return [a.strip().lower() for a in self.EMAIL_ALERT_SENDER_EXCLUDES.split(",") if a.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Meta's own format: a two-letter language, optionally with a region, as in
# "en", "en_US", "pt_BR".
_LANGUAGE_CODE = re.compile(r"^[a-z]{2}(_[A-Z]{2})?$")


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
        if not settings.PAYSTACK_SECRET_KEY:
            warnings.append(
                "PAYSTACK_SECRET_KEY is unset — checkout will fail, and webhook signatures "
                "cannot be verified (the same key signs them)"
            )
        if settings.PAYSTACK_SECRET_KEY and not (settings.PAYSTACK_PLAN_PRO and settings.PAYSTACK_PLAN_ELITE):
            warnings.append("PAYSTACK_PLAN_PRO / PAYSTACK_PLAN_ELITE are unset — paid tiers cannot be purchased")

    # Checked in every environment, because the cost of getting it wrong is
    # paid in silence: a language name rather than a code sends fine as far as
    # this process can tell, and Meta answers 132001 at 07:30 to nobody.
    if not _LANGUAGE_CODE.match(settings.WHATSAPP_TEMPLATE_LANGUAGE):
        errors.append(
            f"WHATSAPP_TEMPLATE_LANGUAGE is {settings.WHATSAPP_TEMPLATE_LANGUAGE!r} — Meta wants the "
            "language code the template was created in, like 'en' or 'en_US', not the language's name"
        )

    if settings.WHATSAPP_PHONE_NUMBER_ID and not settings.WHATSAPP_BUSINESS_NUMBER:
        warnings.append(
            "WHATSAPP_BUSINESS_NUMBER is unset — users cannot be shown the link that opts them in, "
            "and Meta drops template messages to anyone who has never messaged the business"
        )
    if settings.WHATSAPP_PHONE_NUMBER_ID and not settings.WHATSAPP_APP_SECRET:
        warnings.append(
            "WHATSAPP_APP_SECRET is unset — the webhook will refuse every delivery, so opt-ins and "
            "failed sends stay invisible"
        )

    if errors:
        for e in errors:
            logger.error("Config error: %s", e)
        print("\n".join(f"CONFIG ERROR: {e}" for e in errors), file=sys.stderr)
        raise SystemExit(1)

    for w in warnings:
        logger.warning("Config warning: %s", w)
        print(f"WARNING: {w}", file=sys.stderr)
