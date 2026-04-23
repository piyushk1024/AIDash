from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import uploads, profiler, semantics, dashboard, metabase,cleanup,datasets, insights

# from app.schemas import semantics

app = FastAPI(title="AI Dashboard MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets.router)
app.include_router(uploads.router)
app.include_router(profiler.router)
app.include_router(semantics.router)
app.include_router(dashboard.router)
app.include_router(metabase.router)
app.include_router(insights.router)
app.include_router(cleanup.router)

