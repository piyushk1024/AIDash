from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.services.database import create_pool
from app.routes import (
    uploadsRoute, profilerRoute, semanticsRoute,
    dashboardRoute, cleanupRoute,
    datasetsRoute, insightsRoute, nlDashboardRoute,
    authRoute, agentRoute
)
from app.services.migrationRunner import run_migrations
from app.services.telemetry import setup_telemetry, shutdown_telemetry

import logging
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_telemetry()
    app.state.db_pool = await create_pool()
    await run_migrations(app.state.db_pool)
    yield
    # Shutdown
    await app.state.db_pool.close()
    shutdown_telemetry()


app = FastAPI(title="AI Dashboard MVP", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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