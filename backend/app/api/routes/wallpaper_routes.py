import os
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
import replicate

from app.models import Wallpaper, WallpaperStatusEnum, User
from app.core.database import get_db
from app.api.routes.utils import jwt_utils
from app.schemas import (
    WallpaperCreateSchema,
    WallpaperResponseSchema,
    WallpaperListSchema,
    WallpaperDeleteResponse,
    AISuggestionSchema,
    AISuggestionResponse,
)
from app.core.config import settings

router = APIRouter(prefix="/wallpapers", tags=["Wallpapers"])

WALLPAPER_DIR = "static/wallpapers"
os.makedirs(WALLPAPER_DIR, exist_ok=True)

replicate_client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)

SIZE_MAP = {
    "1:1": (1024, 1024),
    "2:3 Portrait": (832, 1216),
    "2:3 Landscape": (1216, 832),
}

STYLE_SUFFIXES = {
    "Colorful": ", vibrant colors, highly detailed, 8k quality",
    "3D Render": ", CGI, 3D render, octane lighting, product-shot quality",
    "3D Cinematic": ", cinematic lighting, volumetric fog, ray tracing, movie-quality",
    "Photorealistic": ", ultra photorealistic, professional photography, sharp details, natural lighting",
    "Illustration": ", digital illustration, concept art style, clean linework",
    "Oil Painting": ", oil painting style, textured brushstrokes, fine art look",
    "Watercolor": ", watercolor painting style, soft edges, artistic wash textures",
    "Cyberpunk": ", neon lights, futuristic glow, dystopian atmosphere, high contrast",
    "Fantasy": ", magical atmosphere, epic fantasy style, mystical lighting",
    "Anime": ", anime style, expressive eyes, cel-shaded, vibrant colors",
    "Manga": ", manga style, dramatic composition, black-and-white inked lines",
    "Cartoon": ", cartoon style, bold outlines, smooth shading, playful character design",
    "Cartoon (Vector)": ", vector cartoon style, bold outlines, flat colors, Disney-like aesthetic",
    "Disney/Pixar": ", Pixar-style 3D animation, soft lighting, family-friendly character design",
    "Chibi": ", chibi style, cute small characters, oversized expressive eyes",
    "Kawaii": ", kawaii style, super cute, pastel colors, soft rounded shapes",
    "Cel-Shading": ", cel-shaded animation style, bold shadows, clean color blocks",
    "Comic Strip": ", comic strip style, halftone shading, bold ink lines, retro comic look",
    "Steampunk": ", Victorian industrial style, brass textures, gears, retro-futuristic",
}


# ---------------------------
# Background Task: Generate Wallpaper
# ---------------------------
def generate_wallpaper_image(wallpaper_id: str, prompt: str, size: str, style: str, db: Session):
    wallpaper = db.query(Wallpaper).filter(Wallpaper.id == wallpaper_id).first()
    if not wallpaper:
        return

    try:
        width, height = SIZE_MAP.get(size, (1024, 1024))
        style_suffix = STYLE_SUFFIXES.get(style, "")
        final_prompt = f"{prompt}{style_suffix}"

        output = replicate_client.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": final_prompt,
                "width": width,
                "height": height,
                "num_outputs": 1,
                "guidance": 3.5,
                "num_inference_steps": 4,
            },
        )

        if not output or not isinstance(output, list):
            wallpaper.status = WallpaperStatusEnum.failed
            db.commit()
            return

        file_obj = output[0]
        image_bytes = file_obj.read()

        filename = f"{uuid4()}.webp"
        image_path = os.path.join(WALLPAPER_DIR, filename)

        with open(image_path, "wb") as f:
            f.write(image_bytes)

        wallpaper.image_url = filename
        wallpaper.status = WallpaperStatusEnum.completed
        db.commit()

    except Exception:
        wallpaper.status = WallpaperStatusEnum.failed
        db.commit()


# ---------------------------
# AI Suggestion
# ---------------------------
@router.post("/suggest", response_model=AISuggestionResponse)
def suggest_prompt(
    payload: AISuggestionSchema,
    token: dict = Depends(jwt_utils.get_current_user),
):
    system_prompt = (
        "You enhance short prompts for image generation. "
        "Rewrite the user's prompt to be more detailed, vivid, and descriptive. "
        "Keep it short (1–2 sentences). Do not add styles unless the user mentions them."
    )

    response = replicate_client.run(
        "meta/meta-llama-3-70b-instruct",
        input={
            "prompt": f"{system_prompt}\nUser prompt: {payload.prompt}\nEnhanced prompt:",
            "temperature": 0.6,
            "max_tokens": 120,
        },
    )

    enhanced = "".join(response).strip()
    return AISuggestionResponse(suggestion=enhanced)


# ---------------------------
# Create Wallpaper
# ---------------------------
@router.post("/", response_model=WallpaperResponseSchema)
def create_wallpaper(
    payload: WallpaperCreateSchema,
    background_tasks: BackgroundTasks,
    token: dict = Depends(jwt_utils.get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == token["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")

    wallpaper = Wallpaper(
        user_id=user.id,
        prompt=payload.prompt,
        size=payload.size,
        style=payload.style,
        status=WallpaperStatusEnum.pending,
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
        db,
    )

    return wallpaper


# ---------------------------
# Recreate Wallpaper
# ---------------------------
@router.post("/{wallpaper_id}/recreate", response_model=WallpaperResponseSchema)
def recreate_wallpaper(
    wallpaper_id: str,
    background_tasks: BackgroundTasks,
    token: dict = Depends(jwt_utils.get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == token["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")

    original = db.query(Wallpaper).filter(Wallpaper.id == wallpaper_id).first()
    if not original or original.user_id != user.id:
        raise HTTPException(404, "Wallpaper not found")

    new_wallpaper = Wallpaper(
        user_id=user.id,
        prompt=original.prompt,
        size=original.size,
        style=original.style,
        status=WallpaperStatusEnum.pending,
    )
    db.add(new_wallpaper)
    db.commit()
    db.refresh(new_wallpaper)

    background_tasks.add_task(
        generate_wallpaper_image,
        new_wallpaper.id,
        original.prompt,
        original.size,
        original.style,
        db,
    )

    return new_wallpaper


# ---------------------------
# List Wallpapers
# ---------------------------
@router.get("/", response_model=WallpaperListSchema)
def list_wallpapers(
    token: dict = Depends(jwt_utils.get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
):
    user = db.query(User).filter(User.email == token["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")

    wallpapers = (
        db.query(Wallpaper)
        .filter(Wallpaper.user_id == user.id)
        .order_by(Wallpaper.created_at.desc())
        .all()
    )

    for wp in wallpapers:
        if wp.image_url:
            wp.full_image_url = f"{request.base_url}static/wallpapers/{wp.image_url}"

    return {"wallpapers": wallpapers}


# ---------------------------
# Delete Wallpaper
# ---------------------------
@router.delete("/{wallpaper_id}", response_model=WallpaperDeleteResponse)
def delete_wallpaper(
    wallpaper_id: str,
    token: dict = Depends(jwt_utils.get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
):
    user = db.query(User).filter(User.email == token["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")

    wallpaper = db.query(Wallpaper).filter(Wallpaper.id == wallpaper_id).first()
    if not wallpaper or wallpaper.user_id != user.id:
        raise HTTPException(404, "Wallpaper not found")

    deleted_info = WallpaperResponseSchema(
        id=wallpaper.id,
        prompt=wallpaper.prompt,
        size=wallpaper.size,
        style=wallpaper.style,
        created_at=wallpaper.created_at,
    )

    if wallpaper.image_url:
        image_path = os.path.join(WALLPAPER_DIR, wallpaper.image_url)
        if os.path.exists(image_path):
            os.remove(image_path)

    db.delete(wallpaper)
    db.commit()

    return {
        "message": "Wallpaper deleted successfully",
        "deleted_wallpaper": deleted_info,
    }

# ---------------------------
# Download Wallpaper
# ---------------------------
@router.get("/{wallpaper_id}/download")
def download_wallpaper(
    wallpaper_id: str,
    token: dict = Depends(jwt_utils.get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == token["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")

    wallpaper = db.query(Wallpaper).filter(Wallpaper.id == wallpaper_id).first()
    if not wallpaper or wallpaper.user_id != user.id:
        raise HTTPException(404, "Wallpaper not found")

    if not wallpaper.image_url:
        raise HTTPException(400, "Wallpaper image not generated yet")

    file_path = os.path.join(WALLPAPER_DIR, wallpaper.image_url)

    if not os.path.exists(file_path):
        raise HTTPException(404, "Image file not found on server")

    return FileResponse(
        file_path,
        media_type="image/webp",
        filename=wallpaper.image_url
    )

