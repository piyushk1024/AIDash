from fastapi import FastAPI
from app.routes import uploads

app = FastAPI(title = "AI Dashboard MVP")

app.include_router(uploads.router)

