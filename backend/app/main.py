from fastapi import FastAPI
from app.api.routes import auth_routes

# Create FastAPI app instance
app = FastAPI(
    title="AI-Wallpaper Backend",
    description="Backend service for AI-Wallpaper mobile app",
    version="1.0.0"
)

# Include routers with prefixes and tags
app.include_router(auth_routes.router, prefix="/auth", tags=["Authentication"])

# Root endpoint for quick health check
@app.get("/", tags=["Health"])
def root():
    return {"message": "AI-Wallpaper Backend is running 🚀"}

