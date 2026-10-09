import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings, validate_settings_on_startup
from app.core.limiter import limiter
from app.routers import (
    admin,
    applications,
    auth,
    autopilot,
    billing,
    digest,
    health,
    integrations,
    interviews,
    jobs,
    matches,
    negotiation,
    outreach,
    resumes,
    stats,
    users,
    whatsapp,
)
from app.services.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()
validate_settings_on_startup(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="JobQuick AI API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Our own shape, and our own words.

    slowapi's handler answers {"error": "Rate limit exceeded: 10 per 1 hour"}.
    Every other error in this API uses `detail`, so the UI read nothing and
    fell back to a bare "Request failed" — which tells the person neither
    what went wrong nor that waiting would fix it. Behind HTTP/2 there is not
    even a status line to fall back to, because HTTP/2 carries no reason
    phrase.
    """
    logger.info("Rate limit hit: %s %s (%s)", request.method, request.url.path, exc.detail)
    return JSONResponse(
        status_code=429,
        content={"detail": f"You have done that too many times ({exc.detail}). Try again a little later."},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %d (%.1fms)", request.method, request.url.path, response.status_code, duration_ms)
    return response


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(billing.router)
app.include_router(resumes.router)
app.include_router(matches.router)
app.include_router(integrations.router)
app.include_router(outreach.router)
app.include_router(interviews.router)
app.include_router(stats.router)
app.include_router(negotiation.router)
app.include_router(digest.router)
app.include_router(autopilot.router)
app.include_router(whatsapp.router)
app.include_router(admin.router)


@app.get("/")
def root() -> dict:
    return {"name": "JobQuick AI API", "status": "ok"}
