from fastapi import FastAPI
from app.routes import uploads,profiler

app = FastAPI(title = "AI Dashboard MVP")

app.include_router(uploads.router)
app.include_router(profiler.router)

