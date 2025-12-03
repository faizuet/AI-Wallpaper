import os
import base64
import requests
from uuid import uuid4
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.models import Wallpaper, WallpaperStatusEnum, User
from app.core.database import get_db
from app.api.routes.utils import jwt_utils
from app.schemas import (
    WallpaperCreateSchema,
    WallpaperResponseSchema,
    WallpaperListSchema,
    MessageResponse,
    WallpaperDeleteResponse,
)
from app.core.config import settings

# ---------------------------
# Setup
# ---------------------------
router = APIRouter(prefix="/wallpapers", tags=["Wallpapers"])

WALLPAPER_DIR = "static/wallpapers"
os.makedirs(WALLPAPER_DIR, exist_ok=True)

# Mapping UI size options to DeAPI resolution
SIZE_MAP = {
    "1:1": (512, 512),
    "2:3 Portrait": (512, 768),
    "2:3 Landscape": (768, 512)
}

#  Correct deAPI endpoints
DEAPI_IMAGE_URL = "https://deapi.ai/api/v1/txt2img?model=Flux1schnell"
DEAPI_TEXT_URL = "https://deapi.ai/models/textgen/playground"

HEADERS = {
    "Authorization": f"Bearer {settings.DEAPI_API_KEY}",
    "Content-Type": "application/json"
}

# ---------------------------
# AI Generation Function
# ---------------------------
def generate_wallpaper_image(wallpaper_id: str, prompt: str, size: str, style: str, db: Session):
    wallpaper = db.query(Wallpaper).filter(Wallpaper.id == wallpaper_id).first()
    if not wallpaper:
        return

    try:
        full_prompt = f"{prompt}, {style}" if style else prompt
        width, height = SIZE_MAP.get(size, (512, 512))

        payload = {
            "prompt": full_prompt,
            "width": width,
            "height": height,
            "steps": 4,  # Flux1schnell is optimized for very few steps
            "negative_prompt": ""
        }

        response = requests.post(DEAPI_IMAGE_URL, json=payload, headers=HEADERS)

        if response.status_code != 200:
            print("DeAPI ERROR:", response.text)
            wallpaper.status = WallpaperStatusEnum.failed
            db.commit()
            return

        data = response.json()
        # deAPI returns base64 image(s) under "images"
        image_data = data["images"][0]
        image_bytes = base64.b64decode(image_data)

        filename = f"{uuid4()}.png"
        image_path = os.path.join(WALLPAPER_DIR, filename)
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        wallpaper.image_url = filename
        wallpaper.status = WallpaperStatusEnum.completed
        db.commit()

    except Exception as e:
        print("AI generation failed:", e)
        wallpaper.status = WallpaperStatusEnum.failed
        db.commit()

# ---------------------------
# Create Wallpaper Request
# ---------------------------
@router.post("/", response_model=WallpaperResponseSchema, summary="Submit wallpaper generation request")
def create_wallpaper(
    payload: WallpaperCreateSchema,
    background_tasks: BackgroundTasks,
    token: dict = Depends(jwt_utils.get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    user = db.query(User).filter(User.email == token["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    wallpaper = Wallpaper(
        user_id=user.id,
        prompt=payload.prompt,
        size=payload.size,
        style=payload.style,
        status=WallpaperStatusEnum.pending
    )
    db.add(wallpaper)
    db.commit()
    db.refresh(wallpaper)

    background_tasks.add_task(
        generate_wallpaper_image,
        wallpaper.id,
        payload.prompt,
        payload.size,
        payload.style,
        db
    )

    if wallpaper.image_url:
        wallpaper.full_image_url = f"{request.base_url}static/wallpapers/{wallpaper.image_url}"

    return wallpaper

# ---------------------------
# List All Wallpapers for User
# ---------------------------
@router.get("/", response_model=WallpaperListSchema, summary="List all wallpapers for current user")
def list_wallpapers(
    token: dict = Depends(jwt_utils.get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    wallpapers = db.query(Wallpaper)\
        .filter(Wallpaper.user_id == token["user_id"])\
        .order_by(Wallpaper.created_at.desc())\
        .all()

    for wp in wallpapers:
        if wp.image_url:
            wp.full_image_url = f"{request.base_url}static/wallpapers/{wp.image_url}"

    return {"wallpapers": wallpapers}

# ---------------------------
# Delete Wallpaper
# ---------------------------
@router.delete("/{wallpaper_id}", response_model=WallpaperDeleteResponse, summary="Delete a wallpaper")
def delete_wallpaper(
    wallpaper_id: str,
    token: dict = Depends(jwt_utils.get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    wallpaper = db.query(Wallpaper).filter(Wallpaper.id == wallpaper_id).first()
    if not wallpaper or wallpaper.user_id != token["user_id"]:
        raise HTTPException(status_code=404, detail="Wallpaper not found")

    deleted_info = WallpaperResponseSchema(
        id=wallpaper.id,
        prompt=wallpaper.prompt,
        size=wallpaper.size,
        style=wallpaper.style,
        status=wallpaper.status,
        image_url=wallpaper.image_url,
        full_image_url=f"{request.base_url}static/wallpapers/{wallpaper.image_url}" if wallpaper.image_url else None,
        created_at=wallpaper.created_at
    )

    if wallpaper.image_url:
        image_path = os.path.join(WALLPAPER_DIR, wallpaper.image_url)
        if os.path.exists(image_path):
            os.remove(image_path)

    db.delete(wallpaper)
    db.commit()

    return {
        "message": "Wallpaper deleted successfully",
        "deleted_wallpaper": deleted_info
    }

# ---------------------------
# Get One AI Prompt Suggestion
# ---------------------------
@router.get("/suggestion", response_model=str, summary="Get one AI-generated prompt suggestion")
def get_prompt_suggestion(style: str):
    """
    Generate a single creative wallpaper prompt using deAPI textgen.
    """
    try:
        headers = {"Authorization": f"Bearer {settings.DEAPI_API_KEY}"}

        prompt_text = (
            f"You are a creative assistant for an AI wallpaper app. "
            f"Give me exactly one short, imaginative prompt for generating a wallpaper "
            f"in the style of {style}. Keep it one sentence, visually descriptive."
        )

        payload = {
            "prompt": prompt_text,
            "max_output_tokens": 100,
            "temperature": 0.9
        }

        response = requests.post(DEAPI_TEXT_URL, json=payload, headers=headers)

        if response.status_code != 200:
            print("DeAPI TextGen failed:", response.text)
            return f"A surreal landscape in {style} style"

        data = response.json()
        suggestion = data.get("output_text") or f"A surreal landscape in {style} style"
        return suggestion.strip()

    except Exception as e:
        print("Suggestion generation failed:", e)
        return f"A surreal landscape in {style} style"

