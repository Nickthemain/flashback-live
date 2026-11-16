/**
 * FLASHBACK // LIVE - MOBILE UPLOADER CLIENT
 * Interactive guest photo upload portal with live previews, filters & reactions.
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM References
  const fileInput = document.getElementById("fileInput");
  const cameraInput = document.getElementById("cameraInput");
  const dropZone = document.getElementById("dropZone");
  const previewContainer = document.getElementById("previewContainer");
  const previewImage = document.getElementById("previewImage");
  const removePreviewBtn = document.getElementById("removePreviewBtn");
  const filterChips = document.querySelectorAll(".filter-chip");
  const guestNameInput = document.getElementById("guestName");
  const captionInput = document.getElementById("caption");
  const charCounter = document.getElementById("charCounter");
  const reactionTags = document.querySelectorAll(".tag-btn");
  const consentCheckbox = document.getElementById("consentCheckbox");
  const uploadBtn = document.getElementById("uploadBtn");
  const progressContainer = document.getElementById("progressContainer");
  const progressBar = document.getElementById("progressBar");
  const uploadFormCard = document.getElementById("uploadFormCard");
  const successCard = document.getElementById("successCard");
  const successThumb = document.getElementById("successThumb");
  const uploadAnotherBtn = document.getElementById("uploadAnotherBtn");
  const galleryGrid = document.getElementById("galleryGrid");
  const galleryEmpty = document.getElementById("galleryEmpty");
  const totalPhotosStat = document.getElementById("totalPhotosStat");
  const statusBadge = document.getElementById("statusBadge");

  // State
  let currentFile = null;
  let selectedFilter = "normal";
  const SAVED_GUEST_KEY = "flashback_guest_name";

  // 1. Restore Guest Name from localStorage
  const savedName = localStorage.getItem(SAVED_GUEST_KEY);
  if (savedName && guestNameInput) {
    guestNameInput.value = savedName;
  }

  // 2. Drag and Drop Handlers
  if (dropZone) {
    ["dragenter", "dragover"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add("dragover");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove("dragover");
      });
    });

    dropZone.addEventListener("drop", (e) => {
      const dt = e.dataTransfer;
      if (dt.files && dt.files.length > 0) {
        handleFileSelection(dt.files[0]);
      }
    });

    dropZone.addEventListener("click", () => {
      if (fileInput) fileInput.click();
    });
  }

  // 3. File Input Handlers
  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileSelection(e.target.files[0]);
      }
    });
  }

  if (cameraInput) {
    cameraInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileSelection(e.target.files[0]);
      }
    });
  }

  function handleFileSelection(file) {
    if (!file.type.startsWith("image/")) {
      alert("Please select a valid image file (JPEG, PNG, WebP, GIF).");
      return;
    }

    // 15MB size limit check
    if (file.size > 15 * 1024 * 1024) {
      alert("File is too large! Maximum allowed size is 15MB.");
      return;
    }

    currentFile = file;

    // Show Preview
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImage.src = e.target.result;
      previewContainer.style.display = "block";
      dropZone.style.display = "none";
      applyFilterToPreview(selectedFilter);
    };
    reader.readAsDataURL(file);
  }

  // 4. Remove Preview / Reset Selection
  if (removePreviewBtn) {
    removePreviewBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      resetUploadSelection();
    });
  }

  function resetUploadSelection() {
    currentFile = null;
    if (fileInput) fileInput.value = "";
    if (cameraInput) cameraInput.value = "";
    previewImage.src = "";
    previewContainer.style.display = "none";
    dropZone.style.display = "block";
    applyFilterToPreview("normal");
  }

  // 5. Filter Selection
  filterChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      filterChips.forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      selectedFilter = chip.getAttribute("data-filter") || "normal";
      applyFilterToPreview(selectedFilter);
    });
  });

  function applyFilterToPreview(filterName) {
    if (!previewImage) return;
    previewImage.className = "";
    previewImage.classList.add(`filter-${filterName}`);
  }

  // 6. Caption Character Counter & Emoji Quick Tags
  if (captionInput && charCounter) {
    captionInput.addEventListener("input", () => {
      charCounter.textContent = `${captionInput.value.length} / 500`;
    });
  }

  reactionTags.forEach((btn) => {
    btn.addEventListener("click", () => {
      const emoji = btn.getAttribute("data-emoji");
      if (captionInput && emoji) {
        captionInput.value = (captionInput.value + " " + emoji).trim();
        captionInput.dispatchEvent(new Event("input"));
        captionInput.focus();
      }
    });
  });

  // 7. Form Submission & Upload
  if (uploadBtn) {
    uploadBtn.addEventListener("click", async () => {
      if (!currentFile) {
        alert("Please snap a photo or choose an image file first!");
        return;
      }

      if (!consentCheckbox || !consentCheckbox.checked) {
        alert("Please check the consent box to broadcast your photo to the event screen.");
        if (consentCheckbox) consentCheckbox.focus();
        return;
      }

      const guestName = (guestNameInput.value.trim() || "Anonymous Guest");
      localStorage.setItem(SAVED_GUEST_KEY, guestName);
      const caption = captionInput.value.trim();

      // UI state: uploading
      uploadBtn.disabled = true;
      uploadBtn.innerHTML = `<span>Broadcasting...</span>`;
      progressContainer.style.display = "block";
      progressBar.style.width = "30%";

      const formData = new FormData();
      formData.append("file", currentFile);
      formData.append("guest_name", guestName);
      formData.append("caption", caption);
      formData.append("filter_applied", selectedFilter);
      formData.append("consent", "true");

      try {
        // Use XMLHttpRequest to get upload progress
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/upload", true);

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            progressBar.style.width = `${percent}%`;
          }
        };

        xhr.onload = function () {
          if (xhr.status === 201) {
            const response = JSON.parse(xhr.responseText);
            handleUploadSuccess(response);
          } else {
            let errorMsg = "Upload failed. Please try again.";
            try {
              const err = JSON.parse(xhr.responseText);
              if (err.detail) errorMsg = err.detail;
            } catch (_) {}
            alert("Error: " + errorMsg);
            resetUploadButton();
          }
        };

        xhr.onerror = function () {
          alert("Network connection error while uploading.");
          resetUploadButton();
        };

        xhr.send(formData);
      } catch (err) {
        console.error("Upload error:", err);
        alert("An unexpected error occurred during upload.");
        resetUploadButton();
      }
    });
  }

  function resetUploadButton() {
    uploadBtn.disabled = false;
    uploadBtn.innerHTML = `<span>🚀 Broadcast to Big Screen</span>`;
    progressContainer.style.display = "none";
    progressBar.style.width = "0%";
  }

  function handleUploadSuccess(photo) {
    resetUploadButton();
    resetUploadSelection();
    if (consentCheckbox) consentCheckbox.checked = false;
    if (captionInput) {
      captionInput.value = "";
      if (charCounter) charCounter.textContent = "0 / 500";
    }

    // Show Success Card with photo thumbnail
    uploadFormCard.style.display = "none";
    successCard.style.display = "block";
    successThumb.src = photo.url;
    successThumb.className = `success-thumb filter-${photo.filter_applied || "normal"}`;

    // Prepend to mini gallery immediately
    addPhotoToGallery(photo, true);
    updateStats();
  }

  // 8. Upload Another Button
  if (uploadAnotherBtn) {
    uploadAnotherBtn.addEventListener("click", () => {
      successCard.style.display = "none";
      uploadFormCard.style.display = "block";
    });
  }

  // 9. Mini Event Feed & Gallery
  async function loadRecentPhotos() {
    try {
      const res = await fetch("/api/photos?limit=20&order=desc");
      if (!res.ok) return;
      const photos = await res.json();

      if (photos.length > 0 && galleryEmpty) {
        galleryEmpty.style.display = "none";
      }

      galleryGrid.innerHTML = "";
      photos.forEach((photo) => addPhotoToGallery(photo, false));
    } catch (err) {
      console.warn("Could not load gallery:", err);
    }
  }

  function addPhotoToGallery(photo, prepend = false) {
    if (!galleryGrid) return;
    if (galleryEmpty) galleryEmpty.style.display = "none";

    const item = document.createElement("div");
    item.className = "gallery-item";
    item.id = `gallery-item-${photo.id}`;

    const filterClass = photo.filter_applied ? `filter-${photo.filter_applied}` : "filter-normal";

    item.innerHTML = `
      <img src="${photo.url}" alt="${escapeHtml(photo.guest_name)}" class="${filterClass}" loading="lazy">
      <button class="gallery-like-btn" data-id="${photo.id}">
        <span>❤️</span> <span class="like-count">${photo.likes_count || 0}</span>
      </button>
      <div class="gallery-overlay">
        <div class="gallery-guest">${escapeHtml(photo.guest_name)}</div>
        ${photo.caption ? `<div class="gallery-caption">${escapeHtml(photo.caption)}</div>` : ""}
      </div>
    `;

    // Heart reaction click
    const likeBtn = item.querySelector(".gallery-like-btn");
    likeBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      await likePhoto(photo.id, likeBtn);
    });

    if (prepend && galleryGrid.firstChild) {
      galleryGrid.insertBefore(item, galleryGrid.firstChild);
    } else {
      galleryGrid.appendChild(item);
    }
  }

  async function likePhoto(photoId, btnElement) {
    try {
      const res = await fetch(`/api/photos/${photoId}/like`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        const countSpan = btnElement.querySelector(".like-count");
        if (countSpan) countSpan.textContent = data.likes_count;
        btnElement.style.transform = "scale(1.2)";
        setTimeout(() => (btnElement.style.transform = ""), 200);
      }
    } catch (err) {
      console.error("Like error:", err);
    }
  }

  async function updateStats() {
    try {
      const res = await fetch("/api/stats");
      if (res.ok) {
        const stats = await res.json();
        if (totalPhotosStat) totalPhotosStat.textContent = stats.total_photos;
      }
    } catch (_) {}
  }

  // 10. Real-time Live Connection Status & SSE Feed sync for guests
  function initGuestSSE() {
    const eventSource = new EventSource("/api/stream");

    eventSource.addEventListener("connected", () => {
      if (statusBadge) {
        statusBadge.classList.remove("disconnected");
        statusBadge.innerHTML = `<span class="live-dot"></span> LIVE EVENT STREAM`;
      }
    });

    eventSource.addEventListener("new_photo", (e) => {
      try {
        const photo = JSON.parse(e.data);
        // If not already in gallery, add it
        if (!document.getElementById(`gallery-item-${photo.id}`)) {
          addPhotoToGallery(photo, true);
          updateStats();
        }
      } catch (err) {
        console.error("SSE parse error:", err);
      }
    });

    eventSource.addEventListener("photo_liked", (e) => {
      try {
        const data = JSON.parse(e.data);
        const item = document.getElementById(`gallery-item-${data.photo_id}`);
        if (item) {
          const countSpan = item.querySelector(".like-count");
          if (countSpan) countSpan.textContent = data.likes_count;
        }
      } catch (_) {}
    });

    eventSource.addEventListener("photo_deleted", (e) => {
      try {
        const data = JSON.parse(e.data);
        const item = document.getElementById(`gallery-item-${data.photo_id}`);
        if (item) item.remove();
        updateStats();
      } catch (_) {}
    });

    eventSource.onerror = () => {
      if (statusBadge) {
        statusBadge.classList.add("disconnected");
        statusBadge.innerHTML = `<span class="live-dot"></span> RECONNECTING...`;
      }
    };
  }

  function escapeHtml(text) {
    if (!text) return "";
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return text.replace(/[&<>"']/g, (m) => map[m]);
  }

  // Init
  loadRecentPhotos();
  updateStats();
  initGuestSSE();
});

