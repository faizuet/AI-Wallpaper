from fastapi import FastAPI
from app.api.main import api_router

app = FastAPI(title="AI Wallpaper App Backend")

app.include_router(api_router)