# FLASHBACK // LIVE — AI Development Log

This document records the prompt engineering history, design iterations, and defect resolution logs accumulated during the design and development of **FLASHBACK // LIVE**.

---

## 1. Six Key Development Prompts

### Prompt 1: System Scaffolding & Architecture Blueprint
> *"Build a complete, production-ready full-stack web application called 'FLASHBACK // LIVE' — an interactive event photo booth and real-time TV slideshow display using FastAPI, SQLite, SSE, Vanilla HTML5/CSS3/ES6+ JS, and an exact folder structure."*
- **Outcome:** Generated the architectural foundation, dependency baseline in `requirements.txt`, environment configuration, and directory layout separating backend services from static client engines.

### Prompt 2: Database Schema & Async Real-Time SSE Broadcaster
> *"Implement the SQLite database models using SQLAlchemy with Photo and Visitor entities, along with an asynchronous Server-Sent Events broadcaster using asyncio.Queue fan-out and keepalive heartbeat pings in FastAPI."*
- **Outcome:** Created `database.py` and `main.py` with multi-client fan-out queues, SQLite WAL configuration, and persistent HTTP `/api/stream` streaming that gracefully handles client disconnects.

### Prompt 3: Mobile Guest Portal & Camera Capture Interface
> *"Create an interactive, mobile-first guest photo upload portal with drag-and-drop support, camera capture trigger, live aesthetic filters (Cyber Glow, Vintage 90s, Noir Glam, Golden Hour), caption input with emoji shoutout buttons, and upload progress feedback."*
- **Outcome:** Built `templates/upload.html`, `static/css/style.css`, and `static/js/upload.js` with instant client-side preview rendering, `localStorage` guest name caching, and animated progress bars.

### Prompt 4: Fullscreen Smart TV Ken Burns Slideshow Engine
> *"Build a cinematic TV and projector slideshow display engine with Ken Burns pan/zoom motion, dynamic blurred ambient background fill, live QR code generation for mobile onboarding, keyboard remote controls, and instant spotlight interruption when new photos arrive via SSE."*
- **Outcome:** Implemented `templates/display.html` and `static/js/display.js`, including ambient backdrop blur to eliminate widescreen letterboxing, dynamic QR code generation, and animated "NEW PHOTO INCOMING" banners.

### Prompt 5: Comprehensive Automated Testing & Security Suite
> *"Implement a full Pytest suite covering all routes, static asset serving, image validation (disallowed extensions, corrupt files, empty payloads), single photo retrieval, like reactions, moderation deletion, and SSE streaming."*
- **Outcome:** Authored `tests/test_api.py` with 17 test cases executing across all application components, verifying security constraints and API status codes.

### Prompt 6: Privacy Governance & Consent Enforcement
> *"Integrate a mandatory, unchecked-by-default broadcast consent checkbox into both frontend and backend workflows, enforce 5MB JPEG/PNG/WEBP limits with binary magic-byte inspection, and document the visitor identity model."*
- **Outcome:** Added affirmative consent validation on client and server (`consent: bool = Form(False)`), updated the SQLite model with `visitors`, and restricted file types with SOI / PNG / RIFF magic-byte inspection.

---

## 2. Three Critical Bugs Caught & Resolved

### 🐞 Bug 1: Test Upload Artifacts & Orphaned Database Records
- **Symptom:**
  Running initial test suites saved dummy test images directly into the production `flashback-live/uploads/` directory and inserted rows into the production `flashback.db`. When temporary test files were deleted from the filesystem, the database still contained references to non-existent filenames. This caused the frontend gallery and TV display to request missing images and fill the server logs with `HTTP 404 Not Found` errors:
  ```text
  INFO: 127.0.0.1 - "GET /uploads/e856939056294de2943c54928d8f9214.jpg HTTP/1.1" 404 Not Found
  INFO: 127.0.0.1 - "GET /uploads/c370af93bc074bba8b9b5356a169afe2.jpg HTTP/1.1" 404 Not Found
  ```
- **Root Cause:**
  Tests were using the default `UPLOADS_DIR` and default database session instead of an isolated temporary fixture.
- **Resolution:**
  1. Updated `tests/test_api.py` with an autouse pytest fixture using Python's `tempfile.mkdtemp()` and `monkeypatch` to redirect `main_module.UPLOADS_DIR` to an isolated scratch folder that is completely destroyed after each test session.
  2. Executed a database migration script that queried `photos` against filesystem presence and pruned all orphaned rows, leaving only genuine user uploads intact.

---

### 🐞 Bug 2: Browser Favicon 404 Request Flooding
- **Symptom:**
  Every time a mobile browser, TV browser, or desktop client loaded `/` or `/display`, browsers automatically sent secondary requests for `/favicon.ico`, `/apple-touch-icon.png`, and `/apple-touch-icon-precomposed.png`. These returned `HTTP 404 Not Found`, creating unnecessary noise in stdout logs:
  ```text
  INFO: 127.0.0.1 - "GET /favicon.ico HTTP/1.1" 404 Not Found
  INFO: 127.0.0.1 - "GET /apple-touch-icon.png HTTP/1.1" 404 Not Found
  ```
- **Root Cause:**
  FastAPI did not have an explicit route handler for `/favicon.ico` or touch icons, falling through to the default 404 handler.
- **Resolution:**
  Added a dedicated, lightweight endpoint in `app/main.py`:
  ```python
  @app.get("/favicon.ico", include_in_schema=False)
  @app.get("/apple-touch-icon.png", include_in_schema=False)
  @app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
  async def serve_favicon():
      svg_favicon = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100" height="100" rx="20" fill="#07070d"/>
        <circle cx="50" cy="50" r="32" fill="none" stroke="#00f0ff" stroke-width="6"/>
        <circle cx="50" cy="50" r="16" fill="#ff007f"/>
        <text y="75" x="25" font-size="50">⚡</text>
      </svg>"""
      return Response(content=svg_favicon, media_type="image/svg+xml")
  ```
  This immediately eliminated 404 errors across all browser clients while delivering a responsive vector brand favicon.

---

### 🐞 Bug 3: Backend Broadcast Consent Validation Gap
- **Symptom:**
  In early builds, photos could be uploaded and broadcast to the public big screen without explicit confirmation that the attendee consented to public projection. While convenient for internal testing, in a production event this poses privacy and compliance risks.
- **Root Cause:**
  The upload form lacked a mandatory consent mechanism, and the backend route accepted multipart files with only optional metadata (guest name and caption).
- **Resolution:**
  1. **Frontend Integration:** Added an unchecked-by-default checkbox to `templates/upload.html`:
     ```html
     <input type="checkbox" id="consentCheckbox">
     <label for="consentCheckbox">I consent to displaying this photo publicly on the live TV event screen.</label>
     ```
  2. **Client-Side Guard:** Updated `static/js/upload.js` to verify that `consentCheckbox.checked` is true before dispatching the request, alerting users if unchecked and clearing the check after success.
  3. **Backend Enforcement:** Added mandatory parameter `consent: bool = Form(False)` in `app/main.py`. If consent evaluates to false, the backend immediately halts execution with an HTTP 400 response:
     ```python
     if not consent:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="Consent is required to broadcast your photo to the public event display."
         )
     ```
  4. **Automated Verification:** Added `test_upload_without_consent_rejected` to `tests/test_api.py` to ensure this security guarantee remains permanently enforced.

