# FLASHBACK // LIVE — Architectural Assumptions & Policy Rules

This document details the core design decisions, privacy assumptions, data validation rules, and queue handling policies implemented in **FLASHBACK // LIVE**.

---

## 1. Visitor Identification Model

### Context & Design Decision
In a fast-paced live event setting (weddings, corporate celebrations, parties), requiring guests to register an account, verify an email, or sign in via OAuth creates friction that discourages participation.

### Implementation Rules:
- **Low-Friction Guest Identity:** Visitors identify themselves with a self-chosen name or social handle (e.g., *"Maya & Liam"*, *"Sarah C."*). If omitted, the system defaults to `"Anonymous Guest"`.
- **Client-Side Persistence:** Guest names are cached in browser `localStorage` under the key `flashback_guest_name`. Returning visitors do not have to re-enter their name on subsequent snaps.
- **Backend Association:** The backend creates or links a `visitors` table record containing the sanitized guest name, timestamp, and the client's origin IP address (for audit and moderation rate-limiting).
- **No Sensitive PII Collected:** No passwords, phone numbers, or emails are collected or stored.

---

## 2. Unchecked Affirmative Consent Checkbox

### Context & Privacy Requirement
Photos uploaded to **FLASHBACK // LIVE** are immediately projected in high definition onto massive screens in public event spaces. Unintentional or unconfirmed photo broadcasts violate attendee expectations.

### Implementation Rules:
- **Unchecked by Default:** The mobile upload portal displays a mandatory consent checkbox:
  > *"I consent to displaying this photo publicly on the live TV event screen."*
  This checkbox is strictly **unchecked** on initial load and is explicitly reset to unchecked following each submission.
- **Client-Side Validation:** The JavaScript uploader verifies `consentCheckbox.checked === true`. If unchecked, the user is alerted with a focus prompt, preventing network transmission.
- **Strict Server-Side Enforcement:** The FastAPI endpoint `/api/upload` treats consent as a mandatory form field (`consent: bool = Form(False)`). If `consent` is missing or false, the server rejects the upload immediately with `HTTP 400 Bad Request` (`"Consent is required to broadcast your photo to the public event display"`), aborting any file persistence or SSE broadcast.

---

## 3. 5MB File Limit & JPEG / PNG / WEBP Magic-Byte Validation

### Context & Security Vulnerabilities
Accepting public file uploads introduces denial-of-service risks (large file exhaustion) and remote code execution risks (disguised scripts or malicious payloads uploaded with image extensions).

### Implementation Rules:
- **5MB File Size Cap:**
  - Configured via environment variable `MAX_UPLOAD_SIZE_MB=5` (5,242,880 bytes).
  - Enforced in both mobile client (`file.size <= 5 * 1024 * 1024`) and backend (`len(contents) > MAX_UPLOAD_BYTES` returns `HTTP 413 Payload Too Large`).
  - Protects server bandwidth and ensures rapid transmission over crowded event Wi-Fi.
- **Allowed Formats:** Only modern raster formats are allowed: `.jpg`, `.jpeg`, `.png`, and `.webp`. Vector formats (e.g., `.svg`) are blocked to prevent Cross-Site Scripting (XSS).
- **Binary Magic-Byte Inspection:** The application does not trust the `Content-Type` header or file extension provided by the client. The first 32 bytes of every uploaded file are analyzed:
  - **JPEG:** Must begin with the Start-of-Image (SOI) marker `0xFF 0xD8 0xFF`.
  - **PNG:** Must match the 8-byte PNG signature `0x89 0x50 0x4E 0x47 0x0D 0x0A 0x1A 0x0A` (`\x89PNG\r\n\x1a\n`).
  - **WebP:** Must begin with the `RIFF` ASCII marker and contain `WEBP` at byte offset 8.
- **Pillow Image Verification:** After passing magic-byte inspection, the file is parsed by `PIL.Image.open().verify()`. Files that fail structural decoding or are truncated are rejected with `HTTP 400 Bad Request`.

---

## 4. UUID Filename Sanitization & FIFO Queue Rules

### Context & Concurrency Management
Simultaneous uploads from hundreds of attendees can cause file collision, directory traversal exploits, and display ordering conflicts.

### Implementation Rules:
- **UUID Filename Sanitization:**
  - Original guest filenames (which may contain special characters, spaces, or directory traversal attempts like `../../evil.jpg`) are sanitized and stored solely as metadata.
  - The actual file written to disk is assigned an immutable 128-bit UUID4 hexadecimal string:
    ```text
    uploads/{uuid4().hex}.{ext}
    ```
  - Guarantees zero naming collisions and eliminates filesystem traversal vulnerabilities.
- **FIFO Event Queue & SSE Fan-Out:**
  - Real-time updates are distributed via an asynchronous broadcaster using `asyncio.Queue` per connected client.
  - Newly uploaded photos enter a FIFO broadcast queue. Connected TV screens receive the event instantaneously over Server-Sent Events (`/api/stream`).
- **TV Slideshow Spotlight Interrupt:**
  - In normal operation, the TV display cycles through photos chronologically or in rotation using a 6-second interval.
  - When an incoming photo event arrives via SSE, the TV slideshow **interrupts rotation**, triggers a "NEW PHOTO INCOMING" visual alert, and spotlight-renders the new photo immediately for an extended 9-second hero duration before resuming the normal FIFO rotation.

