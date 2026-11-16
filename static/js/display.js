/**
 * FLASHBACK // LIVE - TV & PROJECTOR SLIDESHOW DISPLAY ENGINE
 * Real-time SSE listener, Ken Burns transitions, QR code generator & TV controls.
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM References
  const tvStage = document.getElementById("tvStage");
  const tvBackdrop = document.getElementById("tvBackdrop");
  const tvSlideContainer = document.getElementById("tvSlideContainer");
  const tvHeroImage = document.getElementById("tvHeroImage");
  const tvGuestAvatar = document.getElementById("tvGuestAvatar");
  const tvGuestName = document.getElementById("tvGuestName");
  const tvCaption = document.getElementById("tvCaption");
  const tvTimestamp = document.getElementById("tvTimestamp");
  const tvLikeCount = document.getElementById("tvLikeCount");
  const tvFilterPill = document.getElementById("tvFilterPill");
  const tvAlertBanner = document.getElementById("tvAlertBanner");
  const tvAlertText = document.getElementById("tvAlertText");
  const tvSlideProgress = document.getElementById("tvSlideProgress");
  const tvClock = document.getElementById("tvClock");
  const tvPhotoCounter = document.getElementById("tvPhotoCounter");
  const tvLiveBadge = document.getElementById("tvLiveBadge");
  const tvQrWidget = document.getElementById("tvQrWidget");
  const tvQrBox = document.getElementById("tvQrBox");
  const tvQrUrl = document.getElementById("tvQrUrl");
  const tvEmptyState = document.getElementById("tvEmptyState");
  const tvSlideCard = document.getElementById("tvSlideCard");
  const tvMosaicContainer = document.getElementById("tvMosaicContainer");
  const tvHudHeader = document.getElementById("tvHudHeader");

  // State Variables
  let photos = [];
  let currentIndex = 0;
  let isPaused = false;
  let isMosaicMode = false;
  let slideTimer = null;
  let progressInterval = null;
  const SLIDE_DURATION = 6000; // 6 seconds per slide
  let progressStartTime = 0;
  let currentKenBurnsIndex = 0;

  const kenBurnsEffects = [
    "kenburns-zoom-in",
    "kenburns-pan-left",
    "kenburns-zoom-out",
    "kenburns-pan-right",
  ];

  // 1. Digital Clock in TV HUD
  function updateClock() {
    if (!tvClock) return;
    const now = new Date();
    const hours = now.getHours().toString().padStart(2, "0");
    const minutes = now.getMinutes().toString().padStart(2, "0");
    const seconds = now.getSeconds().toString().padStart(2, "0");
    tvClock.textContent = `${hours}:${minutes}:${seconds}`;
  }
  setInterval(updateClock, 1000);
  updateClock();

  // 2. Fetch Initial Photos & Network Info for QR Code
  async function initTV() {
    await fetchNetworkInfo();
    await loadInitialPhotos();
    initSSEListener();
  }

  async function fetchNetworkInfo() {
    try {
      const res = await fetch("/api/network-info");
      if (!res.ok) return;
      const data = await res.json();
      
      const uploadUrl = data.upload_url || window.location.origin;
      if (tvQrUrl) tvQrUrl.textContent = uploadUrl.replace(/^https?:\/\//, "");

      // Render QR code pointing to mobile upload URL
      generateQRCode(uploadUrl);
    } catch (err) {
      console.warn("Could not retrieve network info:", err);
      generateQRCode(window.location.origin);
    }
  }

  // Generates lightweight QR code via pure SVG or dynamic QR API fallback
  function generateQRCode(text) {
    if (!tvQrBox) return;
    
    // We use a high-reliability, zero-dependency SVG QR matrix generator or clean QR endpoint
    // Fallback image using standard SVG generation
    const qrImg = document.createElement("img");
    qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(
      text
    )}&color=000000&bgcolor=ffffff&margin=1`;
    qrImg.alt = "Scan to Upload";
    qrImg.onload = () => {
      tvQrBox.innerHTML = "";
      tvQrBox.appendChild(qrImg);
    };
    qrImg.onerror = () => {
      // Local fallback representation if offline
      tvQrBox.innerHTML = `
        <div style="font-size:0.65rem; color:#000; text-align:center; font-weight:bold; padding:4px;">
          SCAN:<br/><span style="color:#0070f3;">${text}</span>
        </div>
      `;
    };
  }

  async function loadInitialPhotos() {
    try {
      const res = await fetch("/api/photos?limit=100&order=desc");
      if (!res.ok) return;
      photos = await res.json();

      updateCounter();

      if (photos.length === 0) {
        showEmptyState(true);
      } else {
        showEmptyState(false);
        currentIndex = 0;
        renderSlide(photos[currentIndex]);
        startSlideTimer();
      }
    } catch (err) {
      console.error("Failed to load initial photos:", err);
    }
  }

  function showEmptyState(isEmpty) {
    if (isEmpty) {
      if (tvEmptyState) tvEmptyState.style.display = "flex";
      if (tvSlideContainer) tvSlideContainer.style.display = "none";
      if (tvBackdrop) tvBackdrop.style.backgroundImage = "none";
    } else {
      if (tvEmptyState) tvEmptyState.style.display = "none";
      if (tvSlideContainer) tvSlideContainer.style.display = "flex";
    }
  }

  function updateCounter() {
    if (tvPhotoCounter) {
      tvPhotoCounter.textContent = `${photos.length} MOMENTS`;
    }
  }

  // 3. Slideshow Rotation & Ken Burns Engine
  function renderSlide(photo) {
    if (!photo) return;

    showEmptyState(false);

    // Update Blurred TV Backdrop
    if (tvBackdrop) {
      tvBackdrop.style.backgroundImage = `url('${photo.url}')`;
    }

    // Reset and apply new Ken Burns camera animation
    if (tvHeroImage) {
      tvHeroImage.className = "tv-hero-image";
      currentKenBurnsIndex = (currentKenBurnsIndex + 1) % kenBurnsEffects.length;
      const animationClass = kenBurnsEffects[currentKenBurnsIndex];

      // Add filter if applied
      const filterClass = photo.filter_applied ? `filter-${photo.filter_applied}` : "filter-normal";

      // Trigger reflow to restart CSS animation smoothly
      tvHeroImage.src = photo.url;
      void tvHeroImage.offsetWidth;
      tvHeroImage.classList.add(animationClass, filterClass);
    }

    // Update Overlay Information
    if (tvGuestName) tvGuestName.textContent = photo.guest_name || "Anonymous Guest";
    if (tvGuestAvatar) {
      const initial = (photo.guest_name || "A").trim().charAt(0).toUpperCase();
      tvGuestAvatar.textContent = initial || "📸";
    }

    if (tvCaption) {
      if (photo.caption && photo.caption.trim()) {
        tvCaption.textContent = photo.caption;
        tvCaption.style.display = "block";
      } else {
        tvCaption.style.display = "none";
      }
    }

    if (tvTimestamp) {
      tvTimestamp.textContent = formatRelativeTime(photo.created_at);
    }

    if (tvLikeCount) {
      tvLikeCount.textContent = photo.likes_count || 0;
    }

    if (tvFilterPill) {
      if (photo.filter_applied && photo.filter_applied !== "normal") {
        tvFilterPill.style.display = "inline-flex";
        tvFilterPill.textContent = `✨ ${photo.filter_applied.toUpperCase()}`;
      } else {
        tvFilterPill.style.display = "none";
      }
    }

    // Restart progress bar
    resetProgressBar();
  }

  function nextSlide() {
    if (photos.length === 0) return;
    currentIndex = (currentIndex + 1) % photos.length;
    renderSlide(photos[currentIndex]);
  }

  function prevSlide() {
    if (photos.length === 0) return;
    currentIndex = (currentIndex - 1 + photos.length) % photos.length;
    renderSlide(photos[currentIndex]);
  }

  function startSlideTimer(customDuration = SLIDE_DURATION) {
    stopSlideTimer();
    if (isPaused || photos.length <= 1) return;

    progressStartTime = Date.now();
    progressInterval = setInterval(() => {
      const elapsed = Date.now() - progressStartTime;
      const percent = Math.min((elapsed / customDuration) * 100, 100);
      if (tvSlideProgress) tvSlideProgress.style.width = `${percent}%`;
    }, 50);

    slideTimer = setTimeout(() => {
      nextSlide();
      startSlideTimer(SLIDE_DURATION);
    }, customDuration);
  }

  function stopSlideTimer() {
    if (slideTimer) clearTimeout(slideTimer);
    if (progressInterval) clearInterval(progressInterval);
  }

  function resetProgressBar() {
    if (tvSlideProgress) tvSlideProgress.style.width = "0%";
  }

  function togglePause() {
    isPaused = !isPaused;
    if (isPaused) {
      stopSlideTimer();
      showToast("PAUSED ⏸");
    } else {
      startSlideTimer();
      showToast("PLAYING ▶");
    }
  }

  // 4. Real-Time SSE Listener
  function initSSEListener() {
    const eventSource = new EventSource("/api/stream");

    eventSource.addEventListener("connected", () => {
      if (tvLiveBadge) {
        tvLiveBadge.classList.remove("disconnected");
        tvLiveBadge.innerHTML = `<span class="live-dot"></span> LIVE SYNC`;
      }
    });

    // When ANY visitor uploads a new photo:
    eventSource.addEventListener("new_photo", (e) => {
      try {
        const newPhoto = JSON.parse(e.data);
        handleNewIncomingPhoto(newPhoto);
      } catch (err) {
        console.error("Error processing SSE new_photo:", err);
      }
    });

    // When someone likes a photo:
    eventSource.addEventListener("photo_liked", (e) => {
      try {
        const likeData = JSON.parse(e.data);
        handleIncomingLike(likeData);
      } catch (err) {
        console.error("Error processing SSE photo_liked:", err);
      }
    });

    // When an admin deletes a photo:
    eventSource.addEventListener("photo_deleted", (e) => {
      try {
        const delData = JSON.parse(e.data);
        photos = photos.filter((p) => p.id !== delData.photo_id);
        updateCounter();
        if (photos.length === 0) {
          showEmptyState(true);
        } else {
          currentIndex = currentIndex % photos.length;
          renderSlide(photos[currentIndex]);
        }
      } catch (err) {
        console.error("Error processing SSE photo_deleted:", err);
      }
    });

    eventSource.onerror = () => {
      if (tvLiveBadge) {
        tvLiveBadge.classList.add("disconnected");
        tvLiveBadge.innerHTML = `<span class="live-dot"></span> RECONNECTING...`;
      }
    };
  }

  // 5. Spotlight "NEW PHOTO INCOMING" Reaction
  function handleNewIncomingPhoto(newPhoto) {
    // 1. Add to beginning of photos array
    photos.unshift(newPhoto);
    updateCounter();

    // 2. Trigger visual banner notification
    if (tvAlertBanner && tvAlertText) {
      tvAlertText.textContent = `⚡ NEW PHOTO FROM ${newPhoto.guest_name.toUpperCase()}!`;
      tvAlertBanner.classList.add("active");
      setTimeout(() => {
        tvAlertBanner.classList.remove("active");
      }, 4500);
    }

    // 3. Immediately switch slideshow to this new photo
    currentIndex = 0;
    renderSlide(newPhoto);

    // 4. Give the new photo extended hero time (9 seconds)
    stopSlideTimer();
    startSlideTimer(9000);

    // If mosaic mode is active, refresh the wall
    if (isMosaicMode) {
      renderMosaicWall();
    }
  }

  // 6. Floating Hearts Reaction
  function handleIncomingLike(likeData) {
    // If the liked photo is currently on screen, update like count
    if (photos[currentIndex] && photos[currentIndex].id === likeData.photo_id) {
      photos[currentIndex].likes_count = likeData.likes_count;
      if (tvLikeCount) tvLikeCount.textContent = likeData.likes_count;
    }

    // Spawn floating heart particle
    spawnFloatingHeart();
  }

  function spawnFloatingHeart() {
    const heart = document.createElement("div");
    heart.className = "floating-heart";
    const icons = ["❤️", "💖", "🔥", "✨", "🎉"];
    heart.textContent = icons[Math.floor(Math.random() * icons.length)];

    // Random horizontal position (20% to 80%)
    const leftPercent = 20 + Math.random() * 60;
    heart.style.left = `${leftPercent}%`;
    heart.style.bottom = "120px";

    document.body.appendChild(heart);
    setTimeout(() => {
      heart.remove();
    }, 2600);
  }

  // 7. Mosaic Photo Wall Toggle Mode
  function toggleMosaicMode() {
    isMosaicMode = !isMosaicMode;
    if (isMosaicMode) {
      stopSlideTimer();
      if (tvSlideContainer) tvSlideContainer.style.display = "none";
      if (tvMosaicContainer) {
        tvMosaicContainer.style.display = "grid";
        renderMosaicWall();
      }
      showToast("MOSAIC WALL VIEW 🖼");
    } else {
      if (tvMosaicContainer) tvMosaicContainer.style.display = "none";
      if (tvSlideContainer) tvSlideContainer.style.display = "flex";
      renderSlide(photos[currentIndex]);
      startSlideTimer();
      showToast("SLIDESHOW VIEW 📽");
    }
  }

  function renderMosaicWall() {
    if (!tvMosaicContainer) return;
    tvMosaicContainer.innerHTML = "";
    photos.forEach((photo) => {
      const item = document.createElement("div");
      item.className = "tv-mosaic-item";
      const filterClass = photo.filter_applied ? `filter-${photo.filter_applied}` : "";
      item.innerHTML = `<img src="${photo.url}" alt="${photo.guest_name}" class="${filterClass}" loading="lazy">`;
      item.addEventListener("click", () => {
        // Jump to this photo in slideshow
        const idx = photos.findIndex((p) => p.id === photo.id);
        if (idx !== -1) {
          currentIndex = idx;
          toggleMosaicMode();
        }
      });
      tvMosaicContainer.appendChild(item);
    });
  }

  // 8. Fullscreen Toggle
  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch((err) => {
        console.warn("Fullscreen request denied:", err);
      });
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
  }

  // 9. TV Keyboard & Remote Control Shortcuts
  document.addEventListener("keydown", (e) => {
    switch (e.key) {
      case " ":
        e.preventDefault();
        togglePause();
        break;
      case "ArrowRight":
      case "PageDown":
        e.preventDefault();
        nextSlide();
        startSlideTimer();
        break;
      case "ArrowLeft":
      case "PageUp":
        e.preventDefault();
        prevSlide();
        startSlideTimer();
        break;
      case "f":
      case "F":
        toggleFullscreen();
        break;
      case "q":
      case "Q":
        if (tvQrWidget) tvQrWidget.classList.toggle("hidden");
        break;
      case "g":
      case "G":
        toggleMosaicMode();
        break;
      case "m":
      case "M":
        if (tvHudHeader) tvHudHeader.classList.toggle("hidden");
        break;
      case "l":
      case "L":
        // Test like reaction
        if (photos[currentIndex]) {
          fetch(`/api/photos/${photos[currentIndex].id}/like`, { method: "POST" });
        }
        break;
    }
  });

  // 10. Quick On-screen Toast Notification
  function showToast(msg) {
    let toast = document.getElementById("tvQuickToast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "tvQuickToast";
      toast.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(14, 14, 26, 0.92);
        color: #fff;
        padding: 8px 20px;
        border-radius: 999px;
        font-family: var(--font-mono);
        font-size: 0.9rem;
        z-index: 100;
        border: 1px solid rgba(0,240,255,0.4);
        box-shadow: 0 0 20px rgba(0,240,255,0.3);
        pointer-events: none;
        transition: opacity 0.3s ease;
      `;
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.opacity = "1";
    setTimeout(() => {
      toast.style.opacity = "0";
    }, 1800);
  }

  // 11. Time Formatting Helper
  function formatRelativeTime(dateString) {
    if (!dateString) return "Just now";
    const date = new Date(dateString);
    const now = new Date();
    const diffSec = Math.floor((now - date) / 1000);

    if (diffSec < 30) return "Just now";
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  // Start TV Slideshow System
  initTV();
});

