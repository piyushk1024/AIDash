from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import uploadsRoute, profilerRoute, semanticsRoute, dashboardRoute, metabaseRoute,cleanupRoute,datasetsRoute, insightsRoute, nlDashboardRoute

# from app.schemas import semantics

app = FastAPI(title="AI Dashboard MVP")

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

