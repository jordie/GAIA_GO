/**
 * FeedbackRecorder - Audio and photo feedback recording system
 * Captures audio, photos, app state, errors, and context for admin review
 */
class FeedbackRecorder {
  constructor() {
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.isRecording = false;
    this.stream = null;
    this.recognition = null;
    this.transcript = "";
    this.onStateChange = null;
    this.jsErrors = [];
    this.serverErrors = [];
    this.photos = []; // Array of {data: base64, type: string, name: string}
    this.maxPhotos = 3;
    this.maxPhotoSize = 1024 * 1024; // 1MB after compression

    // Capture JS errors globally
    this.setupErrorCapture();

    // Stop recording when tab loses focus
    this.setupVisibilityHandler();
  }

  setupVisibilityHandler() {
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && this.isRecording) {
        console.log("Tab hidden - stopping feedback recording");
        this.stopRecording();
        // Also close the modal if it's open
        const modal = document.getElementById("feedback-modal");
        if (modal) {
          modal.style.display = "none";
        }
      }
    });

    // Also stop on page unload/navigation
    window.addEventListener("beforeunload", () => {
      if (this.isRecording) {
        this.stopRecording();
      }
    });
  }

  setupErrorCapture() {
    window.addEventListener("error", (event) => {
      this.jsErrors.push({
        message: event.message,
        source: event.filename,
        line: event.lineno,
        col: event.colno,
        timestamp: new Date().toISOString(),
      });
      // Keep only last 10 errors
      if (this.jsErrors.length > 10) {
        this.jsErrors = this.jsErrors.slice(-10);
      }
    });

    window.addEventListener("unhandledrejection", (event) => {
      this.jsErrors.push({
        message:
          "Unhandled Promise: " + (event.reason?.message || event.reason),
        timestamp: new Date().toISOString(),
      });
      if (this.jsErrors.length > 10) {
        this.jsErrors = this.jsErrors.slice(-10);
      }
    });
  }

  async init() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      console.warn(
        "Audio recording not supported in this browser - feedback will be text-only",
      );
      this.audioSupported = false;
      return; // Continue without audio support
    }
    this.audioSupported = true;

    if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
      const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.lang = "en-US";

      this.recognition.onresult = (event) => {
        let finalTranscript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          }
        }
        if (finalTranscript) {
          this.transcript += finalTranscript + " ";
        }
      };

      this.recognition.onerror = (event) => {
        console.warn("Speech recognition error:", event.error);
      };
    }
  }

  async startRecording() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.mediaRecorder = new MediaRecorder(this.stream);
      this.audioChunks = [];
      this.transcript = "";

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.start(100);
      this.isRecording = true;

      if (this.recognition) {
        try {
          this.recognition.start();
        } catch (e) {
          console.warn("Speech recognition start error:", e);
        }
      }

      if (this.onStateChange) this.onStateChange("recording");
      return true;
    } catch (error) {
      console.error("Error starting recording:", error);
      throw error;
    }
  }

  stopRecording() {
    return new Promise((resolve) => {
      // Always stop the stream tracks and recognition, even if recorder is inactive
      this.cleanup();

      if (!this.mediaRecorder || this.mediaRecorder.state === "inactive") {
        this.isRecording = false;
        if (this.onStateChange) this.onStateChange("stopped");
        resolve(null);
        return;
      }

      this.mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(this.audioChunks, { type: "audio/webm" });
        const base64Audio = await this.blobToBase64(audioBlob);

        this.isRecording = false;
        if (this.onStateChange) this.onStateChange("stopped");

        resolve({
          audio: base64Audio,
          transcript: this.transcript.trim(),
        });
      };

      this.mediaRecorder.stop();
    });
  }

  cleanup() {
    // Stop all media stream tracks (releases microphone)
    if (this.stream) {
      this.stream.getTracks().forEach((track) => {
        track.stop();
        console.log("Stopped media track:", track.kind);
      });
      this.stream = null;
    }

    // Stop speech recognition
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch (e) {
        // Ignore errors when stopping
      }
    }
  }

  blobToBase64(blob) {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.readAsDataURL(blob);
    });
  }

  // Photo handling methods
  async addPhoto(file) {
    if (this.photos.length >= this.maxPhotos) {
      throw new Error(`Maximum ${this.maxPhotos} photos allowed`);
    }

    const compressed = await this.compressImage(file);
    this.photos.push({
      data: compressed.data,
      type: compressed.type,
      name: file.name || `photo_${Date.now()}.jpg`,
    });

    return this.photos.length - 1; // Return index
  }

  removePhoto(index) {
    if (index >= 0 && index < this.photos.length) {
      this.photos.splice(index, 1);
    }
  }

  clearPhotos() {
    this.photos = [];
  }

  getPhotos() {
    return [...this.photos];
  }

  async compressImage(file, maxWidth = 1200, quality = 0.8) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");

      img.onload = () => {
        let { width, height } = img;

        // Scale down if needed
        if (width > maxWidth) {
          height = (height * maxWidth) / width;
          width = maxWidth;
        }

        canvas.width = width;
        canvas.height = height;
        ctx.drawImage(img, 0, 0, width, height);

        // Convert to JPEG for compression
        const dataUrl = canvas.toDataURL("image/jpeg", quality);

        // If still too large, reduce quality
        if (dataUrl.length > this.maxPhotoSize && quality > 0.3) {
          this.compressImage(file, maxWidth, quality - 0.1)
            .then(resolve)
            .catch(reject);
        } else {
          resolve({
            data: dataUrl,
            type: "image/jpeg",
          });
        }
      };

      img.onerror = () => reject(new Error("Failed to load image"));

      // Read file as data URL
      const reader = new FileReader();
      reader.onload = (e) => {
        img.src = e.target.result;
      };
      reader.onerror = () => reject(new Error("Failed to read file"));
      reader.readAsDataURL(file);
    });
  }

  async loadHtml2Canvas() {
    // Load html2canvas dynamically if not already loaded
    if (typeof html2canvas !== "undefined") {
      return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src =
        "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js";
      script.onload = resolve;
      script.onerror = () =>
        reject(new Error("Failed to load html2canvas library"));
      document.head.appendChild(script);
    });
  }

  async captureScreenshot() {
    // Load html2canvas if not available
    try {
      await this.loadHtml2Canvas();
    } catch (e) {
      throw new Error("Could not load screenshot library");
    }

    if (typeof html2canvas !== "undefined") {
      try {
        // Hide the feedback modal temporarily for clean screenshot
        const modal = document.querySelector(".feedback-modal");
        const modalWasVisible = modal && modal.classList.contains("active");
        if (modalWasVisible) {
          modal.style.visibility = "hidden";
        }

        const canvas = await html2canvas(document.body, {
          scale: 0.5, // Reduce size
          logging: false,
          useCORS: true,
          allowTaint: true,
          backgroundColor: null,
        });

        // Restore modal visibility
        if (modalWasVisible) {
          modal.style.visibility = "visible";
        }

        const dataUrl = canvas.toDataURL("image/jpeg", 0.7);
        this.photos.push({
          data: dataUrl,
          type: "image/jpeg",
          name: `screenshot_${Date.now()}.jpg`,
        });
        return this.photos.length - 1;
      } catch (e) {
        console.warn("Screenshot capture failed:", e);
        throw new Error("Screenshot capture failed: " + e.message);
      }
    } else {
      throw new Error("Screenshot capture requires html2canvas library");
    }
  }

  // Capture current app state
  captureAppState() {
    const state = {
      timestamp: new Date().toISOString(),
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      scrollY: window.scrollY,
    };

    // Try to capture app-specific state
    // Typing app
    if (window.typingApp) {
      state.typingApp = {
        currentText: window.typingApp.currentText,
        wpm: window.typingApp.wpm,
        accuracy: window.typingApp.accuracy,
        currentLevel: window.typingApp.currentLevel,
      };
    }

    // Reading app
    if (window.currentWord) {
      state.currentWord = window.currentWord;
    }
    if (window.masteredWords) {
      state.masteredWords = window.masteredWords;
    }

    // Math app
    if (window.mathApp || document.querySelector("#math-problem")) {
      const problemEl =
        document.querySelector("#math-problem") ||
        document.querySelector(".problem-display");
      if (problemEl) {
        state.currentProblem = problemEl.textContent;
      }
    }

    // Piano app
    if (window.pianoApp) {
      state.pianoApp = {
        currentExercise: window.pianoApp.currentExercise,
        progress: window.pianoApp.progress,
      };
    }

    return state;
  }

  // Get current word/question being tested
  getCurrentContent() {
    // Reading app - current word
    const wordDisplay = document.querySelector(
      ".word-display, #wordDisplay, .current-word",
    );
    if (wordDisplay) {
      return { type: "word", value: wordDisplay.textContent?.trim() };
    }

    // Math app - current question
    const mathProblem = document.querySelector(
      ".problem-display, #math-problem, .question",
    );
    if (mathProblem) {
      return { type: "question", value: mathProblem.textContent?.trim() };
    }

    // Typing app - current text
    const typingText = document.querySelector(".text-display, #text-display");
    if (typingText) {
      return {
        type: "text",
        value: typingText.textContent?.trim()?.substring(0, 100),
      };
    }

    return { type: "unknown", value: "" };
  }

  getBrowserInfo() {
    return `${navigator.userAgent} | Screen: ${screen.width}x${screen.height}`;
  }
}

/**
 * FeedbackButton - UI component for feedback recording with ? icon
 */
class FeedbackButton {
  constructor(options = {}) {
    this.recorder = new FeedbackRecorder();
    this.button = null;
    this.modal = null;
    this.isOpen = false;
    this.appContext = options.appContext || this.detectAppContext();
    this.onSuccess = options.onSuccess || (() => {});
    this.onError = options.onError || ((e) => console.error(e));
  }

  detectAppContext() {
    const path = window.location.pathname;
    if (path.includes("/typing")) return "typing";
    if (path.includes("/math")) return "math";
    if (path.includes("/reading")) return "reading";
    if (path.includes("/piano")) return "piano";
    if (path.includes("/dashboard")) return "dashboard";
    return "general";
  }

  async init() {
    await this.recorder.init();
    this.createButton();
    this.createModal();
    this.injectStyles();
  }

  injectStyles() {
    if (document.getElementById("feedback-styles")) return;

    const styles = document.createElement("style");
    styles.id = "feedback-styles";
    styles.textContent = `
            .feedback-btn {
                background: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.2);
                color: white;
                width: 36px;
                height: 36px;
                border-radius: 50%;
                cursor: pointer;
                font-size: 18px;
                font-weight: bold;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s ease;
                margin-right: 8px;
            }
            .feedback-btn:hover {
                background: rgba(255, 255, 255, 0.25);
                transform: scale(1.1);
            }
            .feedback-btn-fixed {
                position: fixed;
                top: 15px;
                right: 200px;
                z-index: 9999;
                background: #667eea;
            }
            .feedback-modal {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                z-index: 10000;
                align-items: center;
                justify-content: center;
            }
            .feedback-modal.active {
                display: flex;
            }
            .feedback-modal-content {
                background: white;
                border-radius: 16px;
                width: 90%;
                max-width: 450px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                overflow: hidden;
            }
            .feedback-modal-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 16px 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .feedback-modal-header h3 {
                margin: 0;
                font-size: 1.1rem;
            }
            .feedback-close {
                background: none;
                border: none;
                color: white;
                font-size: 24px;
                cursor: pointer;
                padding: 0;
                line-height: 1;
            }
            .feedback-modal-body {
                padding: 20px;
            }
            .feedback-modal-body p {
                margin: 0 0 16px 0;
                color: #666;
                font-size: 0.95rem;
            }
            .feedback-record-area {
                text-align: center;
                padding: 20px 0;
            }
            .feedback-record-btn {
                width: 100px;
                height: 100px;
                border-radius: 50%;
                border: none;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                cursor: pointer;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                margin: 0 auto;
                transition: all 0.2s ease;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            }
            .feedback-record-btn:hover {
                transform: scale(1.05);
            }
            .feedback-record-btn.recording {
                background: linear-gradient(135deg, #f44336 0%, #e91e63 100%);
                animation: pulse 1s infinite;
            }
            @keyframes pulse {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.05); }
            }
            .feedback-record-btn .record-icon {
                font-size: 32px;
                margin-bottom: 4px;
            }
            .feedback-record-btn .record-text {
                font-size: 11px;
                font-weight: 500;
            }
            .feedback-status {
                margin-top: 12px;
                font-size: 0.9rem;
                min-height: 20px;
            }
            .feedback-status.recording {
                color: #f44336;
            }
            .feedback-status.stopped {
                color: #4CAF50;
            }
            .feedback-status.error {
                color: #f44336;
            }
            .feedback-status.success {
                color: #4CAF50;
            }
            .feedback-transcript {
                margin-top: 12px;
                padding: 10px;
                background: #f5f5f5;
                border-radius: 8px;
                font-size: 0.85rem;
                color: #666;
                max-height: 100px;
                overflow-y: auto;
            }
            .feedback-transcript:empty {
                display: none;
            }
            .feedback-photo-section {
                margin-top: 16px;
                padding-top: 16px;
                border-top: 1px solid #eee;
            }
            .feedback-photo-section h4 {
                margin: 0 0 12px 0;
                font-size: 0.9rem;
                color: #666;
            }
            .feedback-photo-buttons {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
            }
            .feedback-photo-btn {
                background: #f5f5f5;
                border: 1px dashed #ccc;
                padding: 8px 12px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 0.85rem;
                display: flex;
                align-items: center;
                gap: 6px;
                transition: all 0.2s;
            }
            .feedback-photo-btn:hover {
                background: #e8e8e8;
                border-color: #999;
            }
            .feedback-photo-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .feedback-photo-previews {
                display: flex;
                gap: 8px;
                margin-top: 12px;
                flex-wrap: wrap;
            }
            .feedback-photo-preview {
                position: relative;
                width: 80px;
                height: 80px;
                border-radius: 8px;
                overflow: hidden;
                border: 1px solid #ddd;
            }
            .feedback-photo-preview img {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }
            .feedback-photo-remove {
                position: absolute;
                top: 2px;
                right: 2px;
                background: rgba(0,0,0,0.6);
                color: white;
                border: none;
                border-radius: 50%;
                width: 20px;
                height: 20px;
                cursor: pointer;
                font-size: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .feedback-photo-remove:hover {
                background: rgba(244,67,54,0.9);
            }
            .feedback-photo-input {
                display: none;
            }
            .feedback-modal-footer {
                padding: 16px 20px;
                border-top: 1px solid #eee;
                display: flex;
                justify-content: flex-end;
                gap: 10px;
            }
            .feedback-cancel-btn {
                background: #f5f5f5;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 500;
                color: #666;
            }
            .feedback-cancel-btn:hover {
                background: #eee;
            }
            .feedback-context {
                margin-top: 12px;
                padding: 10px;
                background: #e3f2fd;
                border-radius: 8px;
                font-size: 0.8rem;
                color: #1976d2;
            }
        `;
    document.head.appendChild(styles);
  }

  createButton() {
    this.button = document.createElement("button");
    this.button.className = "feedback-btn";
    this.button.innerHTML = "?";
    this.button.title = "Send Feedback";
    this.button.onclick = () => this.toggleModal();

    // Try to add to header user section (to the left of username)
    const headerUser = document.querySelector(".unified-header .header-user");
    if (headerUser) {
      // Insert at the beginning (left side)
      headerUser.insertBefore(this.button, headerUser.firstChild);
    } else {
      // Fallback: fixed position
      this.button.classList.add("feedback-btn-fixed");
      document.body.appendChild(this.button);
    }
  }

  createModal() {
    this.modal = document.createElement("div");
    this.modal.className = "feedback-modal";
    this.modal.innerHTML = `
            <div class="feedback-modal-content">
                <div class="feedback-modal-header">
                    <h3>Send Feedback</h3>
                    <button class="feedback-close">&times;</button>
                </div>
                <div class="feedback-modal-body">
                    <p>Press and hold the button to record your feedback. We'll capture the current app state automatically.</p>
                    <div class="feedback-record-area">
                        <button class="feedback-record-btn" id="feedbackRecordBtn">
                            <span class="record-icon">&#127908;</span>
                            <span class="record-text">Hold to Record</span>
                        </button>
                        <div class="feedback-status" id="feedbackStatus"></div>
                    </div>
                    <div class="feedback-transcript" id="feedbackTranscript"></div>
                    <div class="feedback-photo-section">
                        <h4>Attach Photos (optional)</h4>
                        <div class="feedback-photo-buttons">
                            <button class="feedback-photo-btn" id="feedbackScreenshot">
                                <span>&#128438;</span> Screenshot
                            </button>
                            <button class="feedback-photo-btn" id="feedbackAddPhoto">
                                <span>&#128247;</span> Add Photo
                            </button>
                            <button class="feedback-photo-btn" id="feedbackTakePhoto">
                                <span>&#128248;</span> Camera
                            </button>
                        </div>
                        <input type="file" accept="image/*" class="feedback-photo-input" id="feedbackPhotoInput" multiple>
                        <input type="file" accept="image/*" capture="environment" class="feedback-photo-input" id="feedbackCameraInput">
                        <div class="feedback-photo-previews" id="feedbackPhotoPreviews"></div>
                    </div>
                    <div class="feedback-context" id="feedbackContext"></div>
                </div>
                <div class="feedback-modal-footer">
                    <button class="feedback-cancel-btn">Cancel</button>
                </div>
            </div>
        `;
    document.body.appendChild(this.modal);

    // Event listeners
    this.modal.querySelector(".feedback-close").onclick = () => this.close();
    this.modal.querySelector(".feedback-cancel-btn").onclick = () =>
      this.close();

    // Photo event listeners
    this.modal.querySelector("#feedbackAddPhoto").onclick = () => {
      this.modal.querySelector("#feedbackPhotoInput").click();
    };
    this.modal.querySelector("#feedbackTakePhoto").onclick = () => {
      this.modal.querySelector("#feedbackCameraInput").click();
    };
    this.modal.querySelector("#feedbackScreenshot").onclick = () =>
      this.handleScreenshot();
    this.modal.querySelector("#feedbackPhotoInput").onchange = (e) =>
      this.handlePhotoSelect(e);
    this.modal.querySelector("#feedbackCameraInput").onchange = (e) =>
      this.handlePhotoSelect(e);

    const recordBtn = this.modal.querySelector("#feedbackRecordBtn");
    recordBtn.onmousedown = () => this.startRecording();
    recordBtn.onmouseup = () => this.stopRecording();
    recordBtn.onmouseleave = () => {
      if (this.recorder.isRecording) this.stopRecording();
    };
    recordBtn.ontouchstart = (e) => {
      e.preventDefault();
      this.startRecording();
    };
    recordBtn.ontouchend = (e) => {
      e.preventDefault();
      this.stopRecording();
    };

    // Close on backdrop click
    this.modal.onclick = (e) => {
      if (e.target === this.modal) this.close();
    };

    // Update state display
    this.recorder.onStateChange = (state) => {
      const status = this.modal.querySelector("#feedbackStatus");
      const recordBtn = this.modal.querySelector("#feedbackRecordBtn");
      if (state === "recording") {
        status.textContent = "Recording...";
        status.className = "feedback-status recording";
        recordBtn.classList.add("recording");
      } else {
        status.textContent = "Recording complete";
        status.className = "feedback-status stopped";
        recordBtn.classList.remove("recording");
      }
    };
  }

  toggleModal() {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  }

  open() {
    this.modal.classList.add("active");
    this.isOpen = true;
    this.reset();
    this.showContext();
  }

  close() {
    this.modal.classList.remove("active");
    this.isOpen = false;
    if (this.recorder.isRecording) {
      this.recorder.stopRecording();
    }
  }

  reset() {
    this.modal.querySelector("#feedbackStatus").textContent = "";
    this.modal.querySelector("#feedbackTranscript").textContent = "";
    this.modal.querySelector("#feedbackPhotoPreviews").innerHTML = "";
    this.recorder.clearPhotos();
    this.recordedData = null;
  }

  async handlePhotoSelect(event) {
    const files = event.target.files;
    if (!files.length) return;

    const status = this.modal.querySelector("#feedbackStatus");

    for (const file of files) {
      if (this.recorder.photos.length >= this.recorder.maxPhotos) {
        status.textContent = `Maximum ${this.recorder.maxPhotos} photos allowed`;
        status.className = "feedback-status error";
        break;
      }

      try {
        status.textContent = "Processing photo...";
        await this.recorder.addPhoto(file);
        this.updatePhotoPreviews();
        status.textContent = "";
      } catch (error) {
        status.textContent = "Error: " + error.message;
        status.className = "feedback-status error";
      }
    }

    // Reset file input
    event.target.value = "";
    this.updatePhotoButtons();
  }

  async handleScreenshot() {
    const status = this.modal.querySelector("#feedbackStatus");
    const screenshotBtn = this.modal.querySelector("#feedbackScreenshot");

    if (this.recorder.photos.length >= this.recorder.maxPhotos) {
      status.textContent = `Maximum ${this.recorder.maxPhotos} photos allowed`;
      status.className = "feedback-status error";
      return;
    }

    try {
      status.textContent = "Capturing screenshot...";
      status.className = "feedback-status";
      screenshotBtn.disabled = true;

      await this.recorder.captureScreenshot();
      this.updatePhotoPreviews();
      this.updatePhotoButtons();

      status.textContent = "Screenshot captured!";
      status.className = "feedback-status success";

      // Clear status after 2 seconds
      setTimeout(() => {
        if (status.textContent === "Screenshot captured!") {
          status.textContent = "";
        }
      }, 2000);
    } catch (error) {
      console.error("Screenshot error:", error);
      status.textContent = "Screenshot failed: " + error.message;
      status.className = "feedback-status error";
    } finally {
      screenshotBtn.disabled = false;
    }
  }

  updatePhotoPreviews() {
    const container = this.modal.querySelector("#feedbackPhotoPreviews");
    container.innerHTML = "";

    this.recorder.photos.forEach((photo, index) => {
      const preview = document.createElement("div");
      preview.className = "feedback-photo-preview";
      preview.innerHTML = `
                <img src="${photo.data}" alt="Photo ${index + 1}">
                <button class="feedback-photo-remove" data-index="${index}">&times;</button>
            `;
      container.appendChild(preview);
    });

    // Add remove handlers
    container.querySelectorAll(".feedback-photo-remove").forEach((btn) => {
      btn.onclick = (e) => {
        const index = parseInt(e.target.dataset.index);
        this.recorder.removePhoto(index);
        this.updatePhotoPreviews();
        this.updatePhotoButtons();
      };
    });
  }

  updatePhotoButtons() {
    const addBtn = this.modal.querySelector("#feedbackAddPhoto");
    const cameraBtn = this.modal.querySelector("#feedbackTakePhoto");
    const screenshotBtn = this.modal.querySelector("#feedbackScreenshot");
    const maxReached = this.recorder.photos.length >= this.recorder.maxPhotos;

    addBtn.disabled = maxReached;
    cameraBtn.disabled = maxReached;
    if (screenshotBtn) screenshotBtn.disabled = maxReached;
  }

  showContext() {
    const context = this.modal.querySelector("#feedbackContext");
    const content = this.recorder.getCurrentContent();
    const appName =
      this.appContext.charAt(0).toUpperCase() + this.appContext.slice(1);

    let contextText = `App: ${appName} | URL: ${window.location.pathname}`;
    if (content.value) {
      contextText += ` | Current ${content.type}: "${content.value.substring(
        0,
        50,
      )}${content.value.length > 50 ? "..." : ""}"`;
    }
    context.textContent = contextText;
  }

  async startRecording() {
    try {
      await this.recorder.startRecording();
      this.modal.querySelector(".feedback-submit-btn").disabled = true;
    } catch (error) {
      this.modal.querySelector("#feedbackStatus").textContent =
        "Error: " + error.message;
      this.modal.querySelector("#feedbackStatus").className =
        "feedback-status error";
    }
  }

  async stopRecording() {
    if (!this.recorder.isRecording) return;

    this.recordedData = await this.recorder.stopRecording();
    if (this.recordedData && this.recordedData.audio) {
      if (this.recordedData.transcript) {
        this.modal.querySelector("#feedbackTranscript").textContent =
          "Transcript: " + this.recordedData.transcript;
      }
      // Auto-submit and close when recording stops
      await this.submit();
    }
  }

  async submit() {
    if (!this.recordedData) return;

    const status = this.modal.querySelector("#feedbackStatus");
    status.textContent = "Sending feedback...";

    const content = this.recorder.getCurrentContent();
    const appState = this.recorder.captureAppState();

    try {
      const payload = {
        audio_data: this.recordedData.audio,
        transcript: this.recordedData.transcript,
        photos: this.recorder.getPhotos(), // Include photos
        app_context: this.appContext,
        page_url: window.location.href,
        app_state: appState,
        current_word: content.type === "word" ? content.value : "",
        current_question: content.type === "question" ? content.value : "",
        js_errors: this.recorder.jsErrors,
        server_errors: this.recorder.serverErrors,
        browser_info: this.recorder.getBrowserInfo(),
      };

      const response = await fetch("/api/feedback/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.error || result.message || "Failed to submit feedback",
        );
      }

      status.textContent = "Feedback submitted! Thank you!";
      status.className = "feedback-status success";
      this.onSuccess();

      setTimeout(() => this.close(), 1500);
    } catch (error) {
      console.error("Feedback submission error:", error);
      status.textContent = "Error: " + error.message;
      status.className = "feedback-status error";
      this.onError(error);
      // Close modal after showing error briefly
      setTimeout(() => this.close(), 2000);
    }
  }
}

// Auto-initialize feedback button when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  // Initialize on all pages (including for admin use)
  const feedbackButton = new FeedbackButton();
  feedbackButton.init().catch(console.error);
});
