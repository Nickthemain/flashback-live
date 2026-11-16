import io
import sys
import shutil
import tempfile
from pathlib import Path
import pytest

# Ensure application package is discoverable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from PIL import Image

import app.main as main_module
from app.main import app
from app.database import init_db, Base, engine, Photo

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown_test_env(monkeypatch):
    """Isolate uploads and database per test session."""
    test_upload_dir = Path(tempfile.mkdtemp(prefix="flashback_test_uploads_"))
    monkeypatch.setattr(main_module, "UPLOADS_DIR", test_upload_dir)

    init_db()

    yield

    # Clean up temporary test files
    if test_upload_dir.exists():
        shutil.rmtree(test_upload_dir, ignore_errors=True)


def create_test_image(format="JPEG", size=(100, 100), color="blue") -> io.BytesIO:
    """Helper to generate a real, valid in-memory image for upload testing."""
    buf = io.BytesIO()
    image = Image.new("RGB", size, color=color)
    image.save(buf, format=format)
    buf.seek(0)
    return buf


# ============================================================================
# 1. FRONTEND ROUTE TESTS
# ============================================================================
def test_upload_portal_route():
    """Test mobile upload page serves HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "FLASHBACK" in response.text
    assert "Broadcast" in response.text


def test_display_slideshow_route():
    """Test smart TV display page serves HTML."""
    response = client.get("/display")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "tvStage" in response.text
    assert "tvHeroImage" in response.text


def test_static_assets_served():
    """Test that static CSS and JavaScript files are mounted and accessible."""
    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200

    upload_js_res = client.get("/static/js/upload.js")
    assert upload_js_res.status_code == 200

    display_js_res = client.get("/static/js/display.js")
    assert display_js_res.status_code == 200


# ============================================================================
# 2. NETWORK & STATS API TESTS
# ============================================================================
def test_network_info_endpoint():
    """Test the network information endpoint used for the TV QR code."""
    response = client.get("/api/network-info")
    assert response.status_code == 200
    data = response.json()
    assert "upload_url" in data
    assert "display_url" in data
    assert "max_upload_size_mb" in data
    assert "allowed_extensions" in data


def test_stats_endpoint():
    """Test the event stats endpoint."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_photos" in data
    assert "total_guests" in data
    assert "total_likes" in data


# ============================================================================
# 3. PHOTO UPLOAD & VALIDATION TESTS (EDGE CASES)
# ============================================================================
def test_successful_jpeg_upload():
    """Test uploading a valid JPEG image with metadata."""
    img_data = create_test_image("JPEG", color="purple")
    response = client.post(
        "/api/upload",
        files={"file": ("test_party.jpg", img_data, "image/jpeg")},
        data={
            "guest_name": "Sarah Connor",
            "caption": "Celebrating the night! 🔥",
            "filter_applied": "cyber",
            "consent": "true"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["guest_name"] == "Sarah Connor"
    assert data["caption"] == "Celebrating the night! 🔥"
    assert data["filter_applied"] == "cyber"
    assert data["filename"].endswith(".jpg")
    assert data["url"].startswith("/uploads/")
    assert data["likes_count"] == 0


def test_successful_png_upload_default_name():
    """Test uploading a PNG image without specifying guest name (defaults to Anonymous)."""
    img_data = create_test_image("PNG", color="green")
    response = client.post(
        "/api/upload",
        files={"file": ("dance_floor.png", img_data, "image/png")},
        data={"caption": "Amazing beats", "consent": "true"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["guest_name"] == "Anonymous Guest"
    assert data["filename"].endswith(".png")


def test_upload_without_consent_rejected():
    """Test that submitting an upload without affirmative consent is rejected."""
    img_data = create_test_image("JPEG", color="orange")
    response = client.post(
        "/api/upload",
        files={"file": ("no_consent.jpg", img_data, "image/jpeg")},
        data={"guest_name": "Reluctant Guest", "consent": "false"}
    )
    assert response.status_code == 400
    assert "consent" in response.json()["detail"].lower()


def test_upload_disallowed_extension():
    """Test rejecting files with unauthorized extensions (e.g. .pdf, .exe)."""
    fake_file = io.BytesIO(b"Hello text document")
    response = client.post(
        "/api/upload",
        files={"file": ("malicious_script.sh", fake_file, "text/plain")},
        data={"guest_name": "Hacker", "consent": "true"}
    )
    assert response.status_code == 400
    assert "Invalid file extension" in response.json()["detail"]


def test_upload_empty_file():
    """Test rejecting empty (0-byte) image upload."""
    empty_file = io.BytesIO(b"")
    response = client.post(
        "/api/upload",
        files={"file": ("empty.jpg", empty_file, "image/jpeg")},
        data={"guest_name": "Test", "consent": "true"}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_corrupt_spoofed_image():
    """Test rejecting text content disguised as a .jpg file (magic bytes failure)."""
    fake_img = io.BytesIO(b"This is not a real JPEG image file at all!")
    response = client.post(
        "/api/upload",
        files={"file": ("fake.jpg", fake_img, "image/jpeg")},
        data={"guest_name": "Imposter", "consent": "true"}
    )
    assert response.status_code == 400
    assert "image signatures" in response.json()["detail"].lower()


def test_upload_missing_file_payload():
    """Test 422 error when file field is omitted from multipart request."""
    response = client.post(
        "/api/upload",
        data={"guest_name": "No File", "consent": "true"}
    )
    assert response.status_code == 422


# ============================================================================
# 4. PHOTO RETRIEVAL, LIKING, AND DELETION TESTS
# ============================================================================
def test_list_photos_and_pagination():
    """Test photo list retrieval and pagination parameters."""
    # Ensure at least one photo exists
    img_data = create_test_image("JPEG", color="red")
    client.post(
        "/api/upload",
        files={"file": ("pagination_test.jpg", img_data, "image/jpeg")},
        data={"guest_name": "DJ Mike", "consent": "true"}
    )

    res = client.get("/api/photos?limit=2&order=desc")
    assert res.status_code == 200
    photos = res.json()
    assert isinstance(photos, list)
    assert len(photos) <= 2
    if photos:
        assert "url" in photos[0]
        assert "guest_name" in photos[0]


def test_get_single_photo():
    """Test retrieving a specific photo by ID and 404 for non-existent photo."""
    img_data = create_test_image("JPEG", color="yellow")
    create_res = client.post(
        "/api/upload",
        files={"file": ("single_test.jpg", img_data, "image/jpeg")},
        data={"guest_name": "VIP Guest", "consent": "true"}
    )
    photo_id = create_res.json()["id"]

    res = client.get(f"/api/photos/{photo_id}")
    assert res.status_code == 200
    assert res.json()["id"] == photo_id
    assert res.json()["guest_name"] == "VIP Guest"

    # Non-existent ID
    res_404 = client.get("/api/photos/9999999")
    assert res_404.status_code == 404


def test_like_photo_interaction():
    """Test incrementing likes on a photo."""
    img_data = create_test_image("JPEG", color="pink")
    create_res = client.post(
        "/api/upload",
        files={"file": ("like_test.jpg", img_data, "image/jpeg")},
        data={"guest_name": "Party Fan", "consent": "true"}
    )
    photo_id = create_res.json()["id"]

    # Initial like
    like_res_1 = client.post(f"/api/photos/{photo_id}/like")
    assert like_res_1.status_code == 200
    assert like_res_1.json()["likes_count"] == 1

    # Second like
    like_res_2 = client.post(f"/api/photos/{photo_id}/like")
    assert like_res_2.status_code == 200
    assert like_res_2.json()["likes_count"] == 2

    # Liking non-existent photo
    res_404 = client.post("/api/photos/9999999/like")
    assert res_404.status_code == 404


def test_delete_photo_moderation():
    """Test deleting a photo from DB and disk."""
    img_data = create_test_image("JPEG", color="cyan")
    create_res = client.post(
        "/api/upload",
        files={"file": ("delete_test.jpg", img_data, "image/jpeg")},
        data={"guest_name": "Temporary Photo", "consent": "true"}
    )
    photo_id = create_res.json()["id"]

    # Delete photo
    del_res = client.delete(f"/api/photos/{photo_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Verify photo is gone
    get_res = client.get(f"/api/photos/{photo_id}")
    assert get_res.status_code == 404

    # Deleting again returns 404
    del_404 = client.delete(f"/api/photos/{photo_id}")
    assert del_404.status_code == 404


# ============================================================================
# 5. REAL-TIME SSE STREAM ENDPOINT TESTS
# ============================================================================
def test_sse_stream_connection():
    """Test connecting to the SSE stream endpoint and receiving initial handshake."""
    with client.stream("GET", "/api/stream") as stream:
        assert stream.status_code == 200
        assert "text/event-stream" in stream.headers["content-type"]
        
        # Read the first event
        lines = []
        for line in stream.iter_lines():
            if line:
                lines.append(line)
            if len(lines) >= 2:
                break

        full_output = "\n".join(lines)
        assert "event: connected" in full_output
