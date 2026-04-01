from fastapi import FastAPI
from app.routes import uploads, profiler, semantics, dashboard, metabase

# from app.schemas import semantics

app = FastAPI(title="AI Dashboard MVP")

app.include_router(uploads.router)
app.include_router(profiler.router)
app.include_router(semantics.router)
app.include_router(dashboard.router)
app.include_router(metabase.router)
