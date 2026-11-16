# FLASHBACK // LIVE 📸⚡

> **Interactive Event Photo Booth & Real-Time TV Slideshow Display**

**FLASHBACK // LIVE** is a full-stack, zero-build web application designed for weddings, parties, corporate summits, and festivals. Event guests scan an on-screen QR code on their smartphone, snap or upload photos with instant aesthetic filters, add shoutouts, and watch their memories broadcast **instantaneously** to full-screen TV and projector displays without page reloads or polling.

---

## 🏗️ Tech Stack

- **Backend:** Python 3 with [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy](https://www.sqlalchemy.org/) with SQLite, `python-multipart` for streaming uploads, `python-dotenv` for configuration, and `Pillow` for image integrity verification.
- **Real-Time Pipeline:** Native **Server-Sent Events (SSE)** via `/api/stream` using an asynchronous subscriber fan-out broadcaster (`asyncio.Queue`) with automatic keepalive heartbeat pings.
- **Frontend:** Pure Vanilla HTML5, modern CSS3 (Custom properties, CSS Grid/Flexbox, hardware-accelerated `@keyframes`), and clean ES6+ JavaScript. Served directly as static files by FastAPI for zero build-step friction.
- **Testing:** Comprehensive [Pytest](https://docs.pytest.org/) test suite with isolated temporary directories and full endpoint validation.

---

## ⚡ Quick Start & Run Steps

### 1. Prerequisites
- Python 3.10+ installed on your system.

### 2. Environment Setup
Navigate to the project root and create a virtual environment:
```bash
cd flashback-live
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the template configuration:
```bash
cp .env.example .env
```
*(Default settings use local SQLite `flashback.db`, 5MB upload limit, and port 8000).*

### 5. Launch the Application Server
Run using Uvicorn with auto-reload:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*(Alternatively, execute `./run.sh` from the workspace root).*

---

## 🌐 Application Host Links

Once the server is running, access the web portals:

| Portal | URL | Description |
|---|---|---|
| **Mobile Guest Photo Booth** | [http://localhost:8000/](http://localhost:8000/) | Mobile-first visitor portal (camera snap, photo filters, shoutouts, reactions) |
| **TV / Projector Display** | [http://localhost:8000/display](http://localhost:8000/display) | Fullscreen TV slideshow with live SSE sync & ambient backdrop |
| **Interactive API Documentation** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI for interactive endpoint testing |
| **Real-Time Event Stream** | [http://localhost:8000/api/stream](http://localhost:8000/api/stream) | Server-Sent Events real-time broadcast endpoint |

> **LAN / Wi-Fi Access:** For guests on the same local Wi-Fi network, access via `http://<YOUR_LOCAL_IP>:8000/` or scan the dynamic QR code displayed on the TV screen.

---

## ⌨️ Smart TV & Projector Remote Controls

When viewing `/display`, control the presentation using keyboard shortcuts or TV remote keys:

- `Space`: Pause / Resume slideshow rotation
- `F`: Toggle Fullscreen display
- `G`: Toggle Mosaic Photo Wall mode vs. Hero Slideshow
- `Q`: Show / Hide floating QR Code widget
- `M`: Toggle HUD overlay (clean cinema mode)
- `←` / `→`: Navigate to previous / next photo slide
- `L`: Trigger a live test floating heart reaction

---

## 🧪 Running Automated Tests

Run the complete Pytest suite:
```bash
pytest tests/test_api.py -v
```

### Test Coverage Highlights:
- **Frontend & Static Assets:** Verifies `/`, `/display`, `/static/css/style.css`, and JS bundles serve HTTP 200.
- **Upload Validation:** Validates genuine JPEG/PNG files, rejects files without consent, rejects disallowed extensions (`.sh`, `.exe`), rejects 0-byte uploads, and blocks spoofed files failing binary magic-byte checks.
- **Data & Moderation:** Tests photo pagination, single photo retrieval, like counters, and deletion moderation.
- **Real-Time SSE:** Connects to `/api/stream` and verifies the persistent event stream and initial handshake event.
- **Test Isolation:** Automatic temporary directory fixtures prevent test files from polluting production storage.
