import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings, validate_settings_on_startup
from app.core.limiter import limiter
from app.routers import (
    admin,
    applications,
    auth,
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


app = FastAPI(title="HuntOps API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.include_router(admin.router)


@app.get("/")
def root() -> dict:
    return {"name": "HuntOps API", "status": "ok"}
