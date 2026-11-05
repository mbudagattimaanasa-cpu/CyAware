/**
 * CyAware — Core Analysis Interfaces Controller
 * File: frontend/js/analysis.js
 * 
 * Implements Stage 3 requirements:
 * 1. Text Analysis (POST /api/analyze/text)
 * 2. File Analysis (POST /api/analyze/file)
 * 3. Image OCR Analysis (POST /api/analyze/image)
 * 4. Conversation Analysis (POST /api/analyze/conversation)
 * 
 * STRICT RULES:
 * - Zero backend simulation or fake prediction scores.
 * - Loading, empty, and validation states for all 4 interfaces.
 * - Responsible AI notices displayed prominently.
 */

(function () {
  'use strict';

  // ==========================================================================
  // 1. Text Analysis Controller
  // ==========================================================================
  function initTextAnalysis() {
    const form = document.getElementById('text-analysis-form');
    const textarea = document.getElementById('text-input');
    const charCounter = document.getElementById('char-count');
    const wordCounter = document.getElementById('word-count');
    const clearBtn = document.getElementById('clear-text-btn');
    const submitBtn = document.getElementById('submit-text-btn');
    const statusContainer = document.getElementById('text-analysis-status');
    const errorContainer = document.getElementById('text-error-feedback');

    if (!form || !textarea) return;

    // Character & Word Counter
    function updateCounters() {
      const text = textarea.value;
      const charCount = text.length;
      const words = text.trim() ? text.trim().split(/\s+/).length : 0;

      if (charCounter) charCounter.textContent = charCount.toLocaleString();
      if (wordCounter) wordCounter.textContent = words.toLocaleString();

      if (charCounter) {
        if (charCount > 3000) {
          charCounter.parentElement.classList.add('limit-danger');
          charCounter.parentElement.classList.remove('limit-warn');
        } else if (charCount > 2000) {
          charCounter.parentElement.classList.add('limit-warn');
          charCounter.parentElement.classList.remove('limit-danger');
        } else {
          charCounter.parentElement.classList.remove('limit-warn', 'limit-danger');
        }
      }

      if (errorContainer && text.trim()) {
        errorContainer.style.display = 'none';
        textarea.classList.remove('is-invalid');
      }
    }

    textarea.addEventListener('input', updateCounters);

    // Clear Button
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        textarea.value = '';
        updateCounters();
        textarea.classList.remove('is-invalid');
        if (errorContainer) errorContainer.style.display = 'none';
        if (statusContainer) statusContainer.style.display = 'none';
        textarea.focus();
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast('Text input cleared.', 'info');
        }
      });
    }

    // Quick Sample Buttons
    document.querySelectorAll('[data-sample-text]').forEach(btn => {
      btn.addEventListener('click', function () {
        const sample = this.getAttribute('data-sample-text');
        textarea.value = sample;
        updateCounters();
        textarea.classList.remove('is-invalid');
        if (errorContainer) errorContainer.style.display = 'none';
        textarea.focus();
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast('Sample text loaded.', 'info');
        }
      });
    });

    // Form Submission
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      const text = textarea.value.trim();

      // Empty Validation
      if (!text) {
        textarea.classList.add('is-invalid');
        if (errorContainer) {
          errorContainer.textContent = 'Please enter or paste text to analyze.';
          errorContainer.style.display = 'flex';
        }
        textarea.focus();
        return;
      }

      // Loading State
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner" style="margin-right: 0.5rem;"></span> Preparing Analysis...';
      }

      // Simulate realistic client processing delay
      setTimeout(async () => {
        try {
          const result = await window.CyAwareAPI.submitTextAnalysis(text);

          if (statusContainer) {
            statusContainer.style.display = 'block';
            statusContainer.innerHTML = `
              <div class="demo-result-card">
                <div class="flex justify-between items-center" style="margin-bottom: 1rem;">
                  <div style="font-weight: 700; font-size: 1.1rem; color: var(--color-primary); display: flex; align-items: center; gap: 0.5rem;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                    Analysis Request Validated
                  </div>
                  <span class="badge" style="background: rgba(0, 210, 255, 0.15); color: var(--color-primary); border-color: rgba(0, 210, 255, 0.4);">Stage 3 Demonstration</span>
                </div>
                <p style="font-size: 0.92rem; color: var(--color-text-main); margin-bottom: 0.75rem;">
                  Your text payload is formatted and ready for the agreed backend endpoint: <code>POST /api/analyze/text</code>.
                </p>
                <div class="alert alert-responsible-ai" style="margin-bottom: 1rem;">
                  <div class="alert-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                  </div>
                  <div class="alert-content">
                    <div class="alert-title">Responsible AI Reminder</div>
                    <p style="margin: 0; font-size: 0.88rem;">
                      A single message does not prove cyberbullying. Automated classifications strictly serve as assistive signals for human review, not automated punishment.
                    </p>
                  </div>
                </div>
                <div style="font-size: 0.82rem; color: var(--color-text-dim); margin-bottom: 0.35rem;">
                  Structured Request Payload for <code>${result.endpoint}</code>:
                </div>
                <pre class="payload-preview-box">${JSON.stringify(result.payload, null, 2)}</pre>
                <div style="margin-top: 1rem; font-size: 0.82rem; color: var(--color-text-dim);">
                  Model classification against agreed categories (<strong>Normal, Insult, Threat, Hate Speech, Toxic/Abusive Language</strong>) will be returned when backend API is connected.
                </div>
              </div>
            `;
            statusContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }

          if (window.CyAwareApp && window.CyAwareApp.showToast) {
            window.CyAwareApp.showToast('Text validated for POST /api/analyze/text.', 'success');
          }
        } catch (err) {
          if (errorContainer) {
            errorContainer.textContent = err.message;
            errorContainer.style.display = 'flex';
          }
        } finally {
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              Analyze Text
            `;
          }
        }
      }, 500);
    });

    updateCounters();
  }

  // ==========================================================================
  // 2. File Analysis Controller
  // ==========================================================================
  function initFileAnalysis() {
    const form = document.getElementById('file-analysis-form');
    const fileInput = document.getElementById('file-input');
    const dropzone = document.getElementById('file-dropzone');
    const fileCard = document.getElementById('file-preview-card');
    const fileNameEl = document.getElementById('file-name');
    const fileSizeEl = document.getElementById('file-size');
    const removeBtn = document.getElementById('file-remove-btn');
    const submitBtn = document.getElementById('submit-file-btn');
    const statusContainer = document.getElementById('file-analysis-status');
    const errorContainer = document.getElementById('file-error-feedback');

    if (!form || !fileInput) return;

    let selectedFile = null;

    function handleFile(file) {
      if (!file) return;

      selectedFile = file;
      if (fileNameEl) fileNameEl.textContent = file.name;
      if (fileSizeEl) fileSizeEl.textContent = (file.size / 1024).toFixed(1) + ' KB';

      if (fileCard) fileCard.style.display = 'flex';
      if (dropzone) dropzone.style.display = 'none';
      if (errorContainer) errorContainer.style.display = 'none';
      if (statusContainer) statusContainer.style.display = 'none';

      if (window.CyAwareApp && window.CyAwareApp.showToast) {
        window.CyAwareApp.showToast(`Selected: ${file.name}`, 'info');
      }
    }

    function clearFile() {
      selectedFile = null;
      fileInput.value = '';
      if (fileCard) fileCard.style.display = 'none';
      if (dropzone) dropzone.style.display = 'block';
      if (statusContainer) statusContainer.style.display = 'none';
      if (errorContainer) errorContainer.style.display = 'none';
    }

    fileInput.addEventListener('change', function () {
      if (this.files && this.files[0]) {
        handleFile(this.files[0]);
      }
    });

    if (removeBtn) {
      removeBtn.addEventListener('click', clearFile);
    }

    // Drag and Drop
    if (dropzone) {
      ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          dropzone.classList.add('dragover');
        });
      });

      ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          dropzone.classList.remove('dragover');
        });
      });

      dropzone.addEventListener('drop', (e) => {
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleFile(e.dataTransfer.files[0]);
        }
      });
    }

    // Form Submission
    form.addEventListener('submit', function (e) {
      e.preventDefault();

      if (!selectedFile) {
        if (errorContainer) {
          errorContainer.textContent = 'Please select a document or text file to analyze.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner" style="margin-right: 0.5rem;"></span> Processing File...';
      }

      setTimeout(async () => {
        try {
          const result = await window.CyAwareAPI.submitFileAnalysis(selectedFile);

          if (statusContainer) {
            statusContainer.style.display = 'block';
            statusContainer.innerHTML = `
              <div class="demo-result-card">
                <div class="flex justify-between items-center" style="margin-bottom: 1rem;">
                  <div style="font-weight: 700; font-size: 1.1rem; color: var(--color-primary); display: flex; align-items: center; gap: 0.5rem;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                    Document File Validated
                  </div>
                  <span class="badge" style="background: rgba(0, 210, 255, 0.15); color: var(--color-primary); border-color: rgba(0, 210, 255, 0.4);">Stage 3 Demonstration</span>
                </div>
                <p style="font-size: 0.92rem; color: var(--color-text-main); margin-bottom: 0.75rem;">
                  File <strong>${result.fileMeta.name}</strong> (${result.fileMeta.sizeFormatted}) is prepared for multipart submission to <code>POST /api/analyze/file</code>.
                </p>
                <div class="alert alert-responsible-ai" style="margin-bottom: 1rem;">
                  <div class="alert-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                  </div>
                  <div class="alert-content">
                    <div class="alert-title">Responsible Document Moderation</div>
                    <p style="margin: 0; font-size: 0.88rem;">
                      Batch documents may contain varied context. Isolated flagged lines should be reviewed by human moderators before taking administrative action.
                    </p>
                  </div>
                </div>
                <div style="font-size: 0.82rem; color: var(--color-text-dim); margin-bottom: 0.35rem;">
                  Prepared Multipart Metadata for <code>${result.endpoint}</code>:
                </div>
                <pre class="payload-preview-box">${JSON.stringify(result.fileMeta, null, 2)}</pre>
              </div>
            `;
            statusContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }

          if (window.CyAwareApp && window.CyAwareApp.showToast) {
            window.CyAwareApp.showToast('File validated for POST /api/analyze/file.', 'success');
          }
        } catch (err) {
          if (errorContainer) {
            errorContainer.textContent = err.message;
            errorContainer.style.display = 'flex';
          }
        } finally {
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              Analyze Document File
            `;
          }
        }
      }, 500);
    });
  }

  // ==========================================================================
  // 3. Image OCR Analysis Controller
  // ==========================================================================
  function initImageAnalysis() {
    const form = document.getElementById('image-analysis-form');
    const imageInput = document.getElementById('image-input');
    const dropzone = document.getElementById('image-dropzone');
    const previewContainer = document.getElementById('image-preview-container');
    const previewImg = document.getElementById('image-preview-img');
    const imageNameEl = document.getElementById('image-name');
    const imageSizeEl = document.getElementById('image-size');
    const removeBtn = document.getElementById('image-remove-btn');
    const submitBtn = document.getElementById('submit-image-btn');
    const statusContainer = document.getElementById('image-analysis-status');
    const errorContainer = document.getElementById('image-error-feedback');

    if (!form || !imageInput) return;

    let selectedImage = null;

    function handleImage(file) {
      if (!file) return;

      if (!file.type.startsWith('image/')) {
        if (errorContainer) {
          errorContainer.textContent = 'Please select a valid image file (PNG, JPG, WebP).';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      selectedImage = file;
      if (imageNameEl) imageNameEl.textContent = file.name;
      if (imageSizeEl) imageSizeEl.textContent = (file.size / 1024).toFixed(1) + ' KB';

      // Load client preview
      const reader = new FileReader();
      reader.onload = function (e) {
        if (previewImg) previewImg.src = e.target.result;
        if (previewContainer) previewContainer.style.display = 'block';
        if (dropzone) dropzone.style.display = 'none';
        if (errorContainer) errorContainer.style.display = 'none';
        if (statusContainer) statusContainer.style.display = 'none';
      };
      reader.readAsDataURL(file);

      if (window.CyAwareApp && window.CyAwareApp.showToast) {
        window.CyAwareApp.showToast(`Loaded screenshot: ${file.name}`, 'info');
      }
    }

    function clearImage() {
      selectedImage = null;
      imageInput.value = '';
      if (previewImg) previewImg.src = '';
      if (previewContainer) previewContainer.style.display = 'none';
      if (dropzone) dropzone.style.display = 'block';
      if (statusContainer) statusContainer.style.display = 'none';
      if (errorContainer) errorContainer.style.display = 'none';
    }

    imageInput.addEventListener('change', function () {
      if (this.files && this.files[0]) {
        handleImage(this.files[0]);
      }
    });

    if (removeBtn) {
      removeBtn.addEventListener('click', clearImage);
    }

    // Drag and Drop
    if (dropzone) {
      ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          dropzone.classList.add('dragover');
        });
      });

      ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          dropzone.classList.remove('dragover');
        });
      });

      dropzone.addEventListener('drop', (e) => {
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleImage(e.dataTransfer.files[0]);
        }
      });
    }

    // Form Submission
    form.addEventListener('submit', function (e) {
      e.preventDefault();

      if (!selectedImage) {
        if (errorContainer) {
          errorContainer.textContent = 'Please select a chat screenshot or image to analyze.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner" style="margin-right: 0.5rem;"></span> Extracting OCR & Classifying...';
      }

      setTimeout(async () => {
        try {
          const result = await window.CyAwareAPI.submitImageAnalysis(selectedImage);

          if (statusContainer) {
            statusContainer.style.display = 'block';
            statusContainer.innerHTML = `
              <div class="demo-result-card">
                <div class="flex justify-between items-center" style="margin-bottom: 1rem;">
                  <div style="font-weight: 700; font-size: 1.1rem; color: var(--color-primary); display: flex; align-items: center; gap: 0.5rem;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                    Screenshot Upload Validated
                  </div>
                  <span class="badge" style="background: rgba(0, 210, 255, 0.15); color: var(--color-primary); border-color: rgba(0, 210, 255, 0.4);">Stage 3 Demonstration</span>
                </div>
                <p style="font-size: 0.92rem; color: var(--color-text-main); margin-bottom: 0.75rem;">
                  Image <strong>${result.imageMeta.name}</strong> (${result.imageMeta.sizeFormatted}) is prepared for OCR analysis at <code>POST /api/analyze/image</code>.
                </p>
                <div class="alert alert-info" style="margin-bottom: 1rem;">
                  <div class="alert-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                  </div>
                  <div class="alert-content">
                    <div class="alert-title">Server-Side OCR Pipeline</div>
                    <p style="margin: 0; font-size: 0.88rem;">
                      Optical Character Recognition (OCR) text extraction is owned by the backend. Once extracted, the NLP model evaluates the textual transcript against the 5 agreed categories.
                    </p>
                  </div>
                </div>
                <div style="font-size: 0.82rem; color: var(--color-text-dim); margin-bottom: 0.35rem;">
                  Submitted Image Metadata for <code>${result.endpoint}</code>:
                </div>
                <pre class="payload-preview-box">${JSON.stringify(result.imageMeta, null, 2)}</pre>
              </div>
            `;
            statusContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }

          if (window.CyAwareApp && window.CyAwareApp.showToast) {
            window.CyAwareApp.showToast('Image validated for POST /api/analyze/image.', 'success');
          }
        } catch (err) {
          if (errorContainer) {
            errorContainer.textContent = err.message;
            errorContainer.style.display = 'flex';
          }
        } finally {
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              Analyze Screenshot OCR
            `;
          }
        }
      }, 500);
    });
  }

  // ==========================================================================
  // 4. Conversation Analysis Controller
  // ==========================================================================
  function initConversationAnalysis() {
    const form = document.getElementById('convo-analysis-form');
    const senderInput = document.getElementById('convo-sender-input');
    const messageInput = document.getElementById('convo-message-input');
    const addMessageBtn = document.getElementById('convo-add-btn');
    const transcriptTextarea = document.getElementById('convo-transcript-input');
    const parseTranscriptBtn = document.getElementById('convo-parse-transcript-btn');
    const previewList = document.getElementById('convo-preview-list');
    const messageCountBadge = document.getElementById('convo-count-badge');
    const clearBtn = document.getElementById('convo-clear-btn');
    const submitBtn = document.getElementById('submit-convo-btn');
    const statusContainer = document.getElementById('convo-analysis-status');
    const errorContainer = document.getElementById('convo-error-feedback');

    if (!form || !previewList) return;

    let conversationMessages = [];

    function renderConversation() {
      previewList.innerHTML = '';

      if (conversationMessages.length === 0) {
        previewList.innerHTML = `
          <div style="text-align: center; padding: 2rem; color: var(--color-text-dim); font-size: 0.9rem;">
            No messages added yet. Add messages individually above or paste a formatted chat transcript.
          </div>
        `;
        if (messageCountBadge) messageCountBadge.textContent = '0 Messages';
        return;
      }

      if (messageCountBadge) {
        messageCountBadge.textContent = `${conversationMessages.length} Message${conversationMessages.length > 1 ? 's' : ''}`;
      }

      conversationMessages.forEach((msg, index) => {
        const bubble = document.createElement('div');
        bubble.className = 'convo-bubble';
        bubble.innerHTML = `
          <div class="convo-bubble-header">
            <span class="convo-bubble-sender">${escapeHtml(msg.sender)}</span>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-size: 0.75rem; color: var(--color-text-dim);">${escapeHtml(msg.time || '')}</span>
              <button type="button" class="convo-bubble-remove" data-index="${index}" aria-label="Remove message">&times;</button>
            </div>
          </div>
          <div class="convo-bubble-text">${escapeHtml(msg.message)}</div>
        `;
        previewList.appendChild(bubble);
      });

      // Attach remove handlers
      previewList.querySelectorAll('.convo-bubble-remove').forEach(btn => {
        btn.addEventListener('click', function () {
          const idx = parseInt(this.getAttribute('data-index'), 10);
          conversationMessages.splice(idx, 1);
          renderConversation();
        });
      });

      if (errorContainer) errorContainer.style.display = 'none';
    }

    function addMessage(sender, message) {
      if (!sender.trim() || !message.trim()) return false;

      const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      conversationMessages.push({
        sender: sender.trim(),
        message: message.trim(),
        time: timeStr
      });

      renderConversation();
      return true;
    }

    // Add individual message
    if (addMessageBtn && senderInput && messageInput) {
      addMessageBtn.addEventListener('click', function () {
        const sender = senderInput.value;
        const msg = messageInput.value;

        if (!sender.trim()) {
          senderInput.classList.add('is-invalid');
          senderInput.focus();
          return;
        }
        senderInput.classList.remove('is-invalid');

        if (!msg.trim()) {
          messageInput.classList.add('is-invalid');
          messageInput.focus();
          return;
        }
        messageInput.classList.remove('is-invalid');

        if (addMessage(sender, msg)) {
          messageInput.value = '';
          messageInput.focus();
        }
      });
    }

    // Parse transcript paste
    if (parseTranscriptBtn && transcriptTextarea) {
      parseTranscriptBtn.addEventListener('click', function () {
        const raw = transcriptTextarea.value.trim();
        if (!raw) return;

        const lines = raw.split('\n');
        let parsedCount = 0;

        lines.forEach(line => {
          const match = line.match(/^([^:]+):\s*(.+)$/);
          if (match) {
            addMessage(match[1].trim(), match[2].trim());
            parsedCount++;
          } else if (line.trim()) {
            addMessage('Participant', line.trim());
            parsedCount++;
          }
        });

        if (parsedCount > 0) {
          transcriptTextarea.value = '';
          if (window.CyAwareApp && window.CyAwareApp.showToast) {
            window.CyAwareApp.showToast(`Imported ${parsedCount} messages into thread.`, 'success');
          }
        }
      });
    }

    // Clear all messages
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        conversationMessages = [];
        renderConversation();
        if (statusContainer) statusContainer.style.display = 'none';
        if (errorContainer) errorContainer.style.display = 'none';
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast('Conversation thread cleared.', 'info');
        }
      });
    }

    // Sample conversation loader
    document.querySelectorAll('[data-sample-convo]').forEach(btn => {
      btn.addEventListener('click', function () {
        const type = this.getAttribute('data-sample-convo');
        conversationMessages = [];

        if (type === 'heated') {
          addMessage('Alex', 'Did you finish your part of the project?');
          addMessage('Jordan', 'Not yet, I was occupied with other tasks.');
          addMessage('Alex', 'You always make excuses and hold the entire team back.');
          addMessage('Jordan', 'Stop attacking me, I will get it done tonight.');
        } else {
          addMessage('Elena', 'Hey everyone, please remember tomorrow is the deadline for peer review.');
          addMessage('Marcus', 'Thanks for the reminder! Almost done with my draft.');
          addMessage('Elena', 'Great job Marcus, let me know if anyone needs help.');
        }

        renderConversation();
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast('Sample conversation thread loaded.', 'info');
        }
      });
    });

    // Form Submission
    form.addEventListener('submit', function (e) {
      e.preventDefault();

      if (conversationMessages.length === 0) {
        if (errorContainer) {
          errorContainer.textContent = 'Please add at least one message to the conversation thread before submitting.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner" style="margin-right: 0.5rem;"></span> Evaluating Contextual Flow...';
      }

      setTimeout(async () => {
        try {
          const result = await window.CyAwareAPI.submitConversationAnalysis(conversationMessages);

          if (statusContainer) {
            statusContainer.style.display = 'block';
            statusContainer.innerHTML = `
              <div class="demo-result-card">
                <div class="flex justify-between items-center" style="margin-bottom: 1rem;">
                  <div style="font-weight: 700; font-size: 1.1rem; color: var(--color-primary); display: flex; align-items: center; gap: 0.5rem;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                    Conversation Thread Validated
                  </div>
                  <span class="badge" style="background: rgba(0, 210, 255, 0.15); color: var(--color-primary); border-color: rgba(0, 210, 255, 0.4);">Stage 3 Demonstration</span>
                </div>
                <p style="font-size: 0.92rem; color: var(--color-text-main); margin-bottom: 0.75rem;">
                  Thread with <strong>${result.messageCount} messages</strong> formatted for submission to <code>POST /api/analyze/conversation</code>.
                </p>
                <div class="alert alert-responsible-ai" style="margin-bottom: 1rem;">
                  <div class="alert-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                  </div>
                  <div class="alert-content">
                    <div class="alert-title">Contextual Nuance in Multi-Turn Dialogue</div>
                    <p style="margin: 0; font-size: 0.88rem;">
                      Conversation context distinguishes between reciprocal banter and targeted cyberbullying. Model predictions will inform human review rather than trigger automated actions.
                    </p>
                  </div>
                </div>
                <div style="font-size: 0.82rem; color: var(--color-text-dim); margin-bottom: 0.35rem;">
                  Prepared Conversation Payload for <code>${result.endpoint}</code>:
                </div>
                <pre class="payload-preview-box">${JSON.stringify(result.messages, null, 2)}</pre>
              </div>
            `;
            statusContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }

          if (window.CyAwareApp && window.CyAwareApp.showToast) {
            window.CyAwareApp.showToast('Conversation validated for POST /api/analyze/conversation.', 'success');
          }
        } catch (err) {
          if (errorContainer) {
            errorContainer.textContent = err.message;
            errorContainer.style.display = 'flex';
          }
        } finally {
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              Analyze Conversation Thread
            `;
          }
        }
      }, 500);
    });

    renderConversation();
  }

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // Initialize on DOM ready
  document.addEventListener('DOMContentLoaded', function () {
    initTextAnalysis();
    initFileAnalysis();
    initImageAnalysis();
    initConversationAnalysis();
  });
})();

