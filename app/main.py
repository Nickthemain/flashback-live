import os
import io
import json
import uuid
import socket
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Set

from fastapi import (
    FastAPI,
    File,
    UploadFile,
    Form,
    HTTPException,
    Depends,
    Query,
    Request,
    status
)
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from PIL import Image

from .database import init_db, get_db, Photo, Visitor, BASE_DIR
from .schemas import (
    PhotoResponse,
    PhotoLikeResponse,
    StatsResponse,
    DeleteResponse
)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("flashback")

# Paths and environment
UPLOADS_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "5"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ext.strip().lower()
    for ext in os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png,webp").split(",")
}

# Ensure uploads directory exists
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Initialize database
init_db()

# Create FastAPI application
app = FastAPI(
    title="FLASHBACK // LIVE",
    description="Interactive Event Photo Booth & Real-Time TV Slideshow Display",
    version="1.0.0"
)

# CORS Middleware (allows multi-device event access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static and uploaded files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


# ============================================================================
# SSE (SERVER-SENT EVENTS) BROADCASTER
# ============================================================================
class SSEBroadcaster:
    """
    Manages active SSE client connections and broadcasts real-time photo events.
    Thread-safe and async-compatible.
    """
    def __init__(self):
        self._subscribers: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers.add(queue)
            logger.info("SSE client connected. Active subscribers: %d", len(self._subscribers))
        return queue

    async def unsubscribe(self, queue: asyncio.Queue):
        async with self._lock:
            self._subscribers.discard(queue)
            logger.info("SSE client disconnected. Active subscribers: %d", len(self._subscribers))

    async def broadcast(self, event: str, data: dict):
        message = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        async with self._lock:
            subscribers_snapshot = list(self._subscribers)
        
        for queue in subscribers_snapshot:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue is full. Dropping message for slow consumer.")

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


broadcaster = SSEBroadcaster()


# ============================================================================
# FILE VALIDATION HELPERS
# ============================================================================
def validate_magic_bytes(header: bytes, ext: str) -> bool:
    """
    Validates file magic numbers against expected image signatures to prevent
    arbitrary file execution or disguised scripts.
    """
    if ext in {"jpg", "jpeg"}:
        return header.startswith(b"\xFF\xD8\xFF")
    elif ext == "png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    elif ext == "gif":
        return header.startswith(b"GIF87a") or header.startswith(b"GIF89a")
    elif ext == "webp":
        return header.startswith(b"RIFF") and b"WEBP" in header[:16]
    return False


def get_local_ip() -> str:
    """Discovers the local network IP address for the TV QR code."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        # Connect to a public DNS IP (doesn't send data) to resolve preferred interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ============================================================================
# FAVICON & BRAND ASSETS
# ============================================================================
@app.get("/favicon.ico", include_in_schema=False)
@app.get("/apple-touch-icon.png", include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
async def serve_favicon():
    """Serves an inline SVG favicon."""
    svg_favicon = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
      <rect width="100" height="100" rx="20" fill="#07070d"/>
      <circle cx="50" cy="50" r="32" fill="none" stroke="#00f0ff" stroke-width="6"/>
      <circle cx="50" cy="50" r="16" fill="#ff007f"/>
      <text y="75" x="25" font-size="50">⚡</text>
    </svg>"""
    return Response(content=svg_favicon, media_type="image/svg+xml")


# ============================================================================
# FRONTEND TEMPLATE ROUTES
# ============================================================================
@app.get("/", response_class=HTMLResponse)
async def serve_upload_portal():
    """Serves the mobile visitor photo booth portal."""
    template_path = TEMPLATES_DIR / "upload.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="upload.html template missing")
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


@app.get("/display", response_class=HTMLResponse)
async def serve_display_slideshow():
    """Serves the smart TV / projector real-time slideshow display."""
    template_path = TEMPLATES_DIR / "display.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="display.html template missing")
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


# ============================================================================
# REAL-TIME SSE ENDPOINT
# ============================================================================
@app.get("/api/stream")
async def sse_event_stream(request: Request):
    """
    Server-Sent Events (SSE) endpoint.
    Maintains a persistent HTTP connection to broadcast newly uploaded photos,
    live reactions/likes, and heartbeat pings to TV displays.
    """
    queue = await broadcaster.subscribe()

    async def event_generator():
        # Send initial connected handshake event
        initial_data = json.dumps({
            "status": "connected",
            "message": "Connected to FLASHBACK // LIVE stream",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        yield f"event: connected\ndata: {initial_data}\n\n"

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for message with timeout to emit heartbeat ping
                    message = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield message
                except asyncio.TimeoutError:
                    # Send lightweight SSE comment keep-alive ping
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ============================================================================
# PHOTO UPLOAD & API ROUTES
# ============================================================================
@app.post("/api/upload", response_model=PhotoResponse, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    request: Request,
    file: UploadFile = File(..., description="Uploaded image file"),
    guest_name: Optional[str] = Form("Anonymous Guest"),
    caption: Optional[str] = Form(""),
    filter_applied: Optional[str] = Form("normal"),
    consent: bool = Form(False, description="Affirmative consent to broadcast to public display"),
    db: Session = Depends(get_db)
):
    """
    Accepts mobile guest photo uploads, validates magic bytes and image integrity,
    enforces visitor broadcast consent, records visitor identity, persists the file,
    and immediately broadcasts to TV screens via SSE.
    """
    # 0. Enforce explicit broadcast consent
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent is required to broadcast your photo to the public event display."
        )

    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file was provided for upload."
        )

    # 1. Sanitize filename and extract extension
    raw_filename = file.filename
    ext = raw_filename.rsplit(".", 1)[-1].lower() if "." in raw_filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file extension '.{ext}'. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 2. Read content & validate file size
    contents = await file.read()
    file_size = len(contents)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (0 bytes)."
        )

    if file_size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {MAX_UPLOAD_SIZE_MB}MB."
        )

    # 3. Validate magic bytes / image header
    if not validate_magic_bytes(contents[:32], ext):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match standard image signatures."
        )

    # 4. Verify image integrity with Pillow
    try:
        image = Image.open(io.BytesIO(contents))
        image.verify()
        mime_type = Image.MIME.get(image.format, file.content_type or f"image/{ext}")
    except Exception as e:
        logger.warning("Corrupt image upload attempted: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is corrupted or not a valid image."
        )

    # 5. Generate secure, unique filename
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    target_path = UPLOADS_DIR / unique_filename

    # 6. Save image to disk
    try:
        with open(target_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        logger.error("Failed to write image to disk: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save image to server storage."
        )

    # 7. Sanitize text fields
    clean_guest_name = (guest_name or "Anonymous Guest").strip()[:100]
    if not clean_guest_name:
        clean_guest_name = "Anonymous Guest"
    clean_caption = (caption or "").strip()[:500]
    clean_filter = (filter_applied or "normal").strip().lower()[:50]

    # 8. Record / associate Visitor identity
    client_ip = request.client.host if request.client else "unknown"
    visitor = db.query(Visitor).filter(Visitor.guest_name == clean_guest_name).first()
    if not visitor:
        visitor = Visitor(
            guest_name=clean_guest_name,
            ip_address=client_ip,
            created_at=datetime.now(timezone.utc)
        )
        db.add(visitor)
        db.flush()

    # 9. Create database record
    db_photo = Photo(
        visitor_id=visitor.id,
        filename=unique_filename,
        original_filename=raw_filename[:255],
        guest_name=clean_guest_name,
        caption=clean_caption,
        filter_applied=clean_filter,
        file_size=file_size,
        mime_type=mime_type,
        likes_count=0,
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_photo)
    db.commit()
    db.refresh(db_photo)

    photo_dict = db_photo.to_dict()

    # 9. Real-Time Broadcast to all connected TV displays
    await broadcaster.broadcast("new_photo", photo_dict)
    logger.info("New photo uploaded (#%d by '%s'). Broadcasted to %d display(s).",
                db_photo.id, clean_guest_name, broadcaster.subscriber_count)

    return photo_dict


@app.get("/api/photos", response_model=List[PhotoResponse])
async def list_photos(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """Retrieves paginated event photos for the gallery and display carousel."""
    query = db.query(Photo)
    if order == "desc":
        query = query.order_by(desc(Photo.created_at))
    else:
        query = query.order_by(Photo.created_at)

    photos = query.offset(offset).limit(limit).all()
    return [p.to_dict() for p in photos]


@app.get("/api/photos/{photo_id}", response_model=PhotoResponse)
async def get_photo(photo_id: int, db: Session = Depends(get_db)):
    """Retrieves a single photo by its database ID."""
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return photo.to_dict()


@app.post("/api/photos/{photo_id}/like", response_model=PhotoLikeResponse)
async def like_photo(photo_id: int, db: Session = Depends(get_db)):
    """
    Increments like reactions on a photo and broadcasts a live reaction
    event to connected screens.
    """
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    photo.likes_count += 1
    db.commit()
    db.refresh(photo)

    # Broadcast like reaction
    await broadcaster.broadcast("photo_liked", {
        "photo_id": photo.id,
        "likes_count": photo.likes_count,
        "guest_name": photo.guest_name
    })

    return PhotoLikeResponse(
        id=photo.id,
        likes_count=photo.likes_count,
        message="Liked successfully"
    )


@app.delete("/api/photos/{photo_id}", response_model=DeleteResponse)
async def delete_photo(photo_id: int, db: Session = Depends(get_db)):
    """Deletes a photo from the database and local storage (moderation)."""
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    file_path = UPLOADS_DIR / photo.filename
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            logger.warning("Could not delete file %s from disk: %s", photo.filename, str(e))

    db.delete(photo)
    db.commit()

    # Broadcast removal to TV displays
    await broadcaster.broadcast("photo_deleted", {"photo_id": photo_id})

    return DeleteResponse(
        success=True,
        message=f"Photo #{photo_id} successfully deleted",
        deleted_id=photo_id
    )


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """Calculates live event statistics."""
    total_photos = db.query(Photo).count()
    total_guests = db.query(func.count(func.distinct(Photo.guest_name))).scalar() or 0
    total_likes = db.query(func.sum(Photo.likes_count)).scalar() or 0
    latest_photo = db.query(Photo).order_by(desc(Photo.created_at)).first()

    return StatsResponse(
        total_photos=total_photos,
        total_guests=total_guests,
        total_likes=total_likes,
        latest_photo=latest_photo.to_dict() if latest_photo else None
    )


@app.get("/api/network-info")
async def get_network_info(request: Request):
    """
    Returns server network address and host information so the TV display
    can render a dynamic, scannable QR code directing mobile phones to the upload page.
    """
    port = int(os.getenv("PORT", "8000"))
    local_ip = get_local_ip()
    host_header = request.headers.get("host", f"{local_ip}:{port}")

    return {
        "local_ip": local_ip,
        "port": port,
        "host": host_header,
        "upload_url": f"http://{host_header}/",
        "display_url": f"http://{host_header}/display",
        "lan_upload_url": f"http://{local_ip}:{port}/",
        "lan_display_url": f"http://{local_ip}:{port}/display",
        "max_upload_size_mb": MAX_UPLOAD_SIZE_MB,
        "allowed_extensions": list(ALLOWED_EXTENSIONS)
    }
