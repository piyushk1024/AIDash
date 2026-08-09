from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.services.database import create_pool
from app.services.quotaGuard import init_quota_guard, QuotaExceededError, get_last_quota_status
from app.routes import (
    uploadsRoute, profilerRoute, semanticsRoute,
    dashboardRoute, cleanupRoute,
    datasetsRoute, insightsRoute, nlDashboardRoute,
    authRoute, agentRoute, launchRoute,feedbackAdminRoute, quotaRoute
)
from app.services.migrationRunner import run_migrations
from app.services.telemetry import setup_telemetry, shutdown_telemetry
from app.config import settings


import logging
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_telemetry()
    app.state.db_pool = await create_pool()
    await run_migrations(app.state.db_pool)
    init_quota_guard(app.state.db_pool)
    yield
    # Shutdown
    await app.state.db_pool.close()
    shutdown_telemetry()


_is_prod = settings.ENVIRONMENT == "production"

app = FastAPI(
    title="AI Dashboard MVP",
    lifespan=lifespan,
    swagger_ui_parameters={"syntaxHighlight": False},
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Quota-Remaining", "X-Quota-Limit"],
)

@app.middleware("http")
async def add_quota_headers(request, call_next):
    response = await call_next(request)
    status = get_last_quota_status()
    if status and not status["unlimited"]:
        response.headers["X-Quota-Remaining"] = str(status["remaining"])
        response.headers["X-Quota-Limit"] = str(status["limit"])
    return response


@app.exception_handler(QuotaExceededError)
async def quota_exceeded_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Daily demo limit reached. Please try again tomorrow."},
    )

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if _is_prod:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


app.include_router(datasetsRoute.router)
app.include_router(uploadsRoute.router)
app.include_router(profilerRoute.router)
app.include_router(semanticsRoute.router)
app.include_router(dashboardRoute.router)
app.include_router(nlDashboardRoute.router)
app.include_router(agentRoute.router)
app.include_router(insightsRoute.router)
app.include_router(authRoute.router)
app.include_router(cleanupRoute.router)
app.include_router(launchRoute.router)
app.include_router(feedbackAdminRoute.router)
app.include_router(quotaRoute.router)