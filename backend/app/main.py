import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings, validate_settings_on_startup
from app.core.limiter import limiter
from app.routers import admin, applications, auth, billing, health, jobs, users

logging.basicConfig(level=logging.INFO)
settings = get_settings()
validate_settings_on_startup(settings)

app = FastAPI(title="HuntOps API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(billing.router)
app.include_router(admin.router)


@app.get("/")
def root() -> dict:
    return {"name": "HuntOps API", "status": "ok"}
