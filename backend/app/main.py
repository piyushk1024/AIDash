# app/main.py
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.services.database import create_pool
from app.routes import (
    uploadsRoute, profilerRoute, semanticsRoute,
    dashboardRoute, metabaseRoute, cleanupRoute,
    datasetsRoute, insightsRoute, nlDashboardRoute,
    authRoute,agentRoute
)
from app.services.migrationRunner import run_migrations
import logging
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.db_pool = await create_pool()
    await run_migrations(app.state.db_pool)
    app.state.http_client = httpx.AsyncClient()
    app.state.metabase_token = None
    app.state.metabase_token_expires = 0.0
    yield
    # Shutdown
    await app.state.db_pool.close()
    await app.state.http_client.aclose()


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
app.include_router(metabaseRoute.router)
app.include_router(insightsRoute.router)
app.include_router(cleanupRoute.router)
app.include_router(nlDashboardRoute.router)
app.include_router(authRoute.router)
app.include_router(agentRoute.router)