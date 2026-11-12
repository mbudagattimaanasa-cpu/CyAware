/**
 * CyAware — Core Analysis Interfaces Controller
 * File: frontend/js/analysis.js
 * 
 * Connects frontend analysis interfaces directly to CyAware backend APIs:
 * 1. Single Text Analysis (POST /api/analyze/text)
 * 2. Document File Batch Analysis (POST /api/analyze/file)
 * 3. Chat Screenshot OCR Analysis (POST /api/analyze/image)
 * 4. Multi-Turn Conversation Analysis (POST /api/analyze/conversation)
 * 
 * Strict Project Rules:
 * - Real backend responses dictate all classifications, confidence scores, and explanations.
 * - Zero simulated, fake, or mock predictions.
 * - Never calibrate or misrepresent confidence scores as absolute probabilities.
 * - Display uncalibrated model decision confidence and responsible AI guidance.
 * - Conversation analysis is strictly ephemeral and never persisted.
 * - Opt-in persistence for text analysis requires authenticated user.
 */

(function () {
  'use strict';

  // Helper: map category to CSS badge class
  function getCategoryBadgeClass(category) {
    switch (category) {
      case 'Normal':
        return 'badge-normal';
      case 'Insult':
        return 'badge-insult';
      case 'Threat':
        return 'badge-threat';
      case 'Hate Speech':
        return 'badge-hate';
      case 'Toxic/Abusive':
      case 'Toxic/Abusive Language':
        return 'badge-toxic';
      default:
        return 'badge-normal';
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ==========================================================================
  // 1. Single Text Analysis Controller
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

    // Check authentication state to conditionally render save opt-in
    let isAuthenticated = false;
    let saveCheckbox = null;

    async function checkAuthForSaveOptin() {
      if (window.CyAwareAPI && typeof window.CyAwareAPI.getMe === 'function') {
        try {
          const res = await window.CyAwareAPI.getMe();
          if (res && res.success && res.data) {
            isAuthenticated = true;
            renderSaveOptinControl();
          }
        } catch {
          isAuthenticated = false;
        }
      }
    }

    function renderSaveOptinControl() {
      if (document.getElementById('text-save-optin-wrapper')) return;

      const optinWrapper = document.createElement('div');
      optinWrapper.id = 'text-save-optin-wrapper';
      optinWrapper.className = 'form-check';
      optinWrapper.style.marginTop = '1rem';
      optinWrapper.innerHTML = `
        <input type="checkbox" id="text-save-optin" class="form-check-input">
        <label for="text-save-optin" class="form-check-label" style="font-size: 0.88rem; color: var(--color-text-muted);">
          Save this analysis to my audit history (Authenticated session active)
        </label>
      `;

      // Insert right before action buttons
      const actionRow = form.querySelector('.flex.justify-between.items-center');
      if (actionRow && actionRow.parentNode) {
        actionRow.parentNode.insertBefore(optinWrapper, actionRow);
      }
      saveCheckbox = document.getElementById('text-save-optin');
    }

    checkAuthForSaveOptin();

    // Character & Word Counter
    function updateCounters() {
      const text = textarea.value;
      const charCount = text.length;
      const words = text.trim() ? text.trim().split(/\s+/).length : 0;

      if (charCounter) charCounter.textContent = charCount.toLocaleString();
      if (wordCounter) wordCounter.textContent = words.toLocaleString();

      if (charCounter && charCounter.parentElement) {
        if (charCount > 2000) {
          charCounter.parentElement.classList.add('limit-danger');
          charCounter.parentElement.classList.remove('limit-warn');
        } else if (charCount > 1800) {
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
        if (statusContainer) {
          statusContainer.style.display = 'none';
          statusContainer.innerHTML = '';
        }
        textarea.focus();
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast('Text input cleared.', 'info');
        }
      });
    }

    // Quick Sample Prompts
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

      // Empty validation
      if (!text) {
        textarea.classList.add('is-invalid');
        if (errorContainer) {
          errorContainer.textContent = 'Please enter or paste text to analyze.';
          errorContainer.style.display = 'flex';
        }
        textarea.focus();
        return;
      }

      // Max characters validation (backend allows 1-2000)
      if (text.length > 2000) {
        textarea.classList.add('is-invalid');
        if (errorContainer) {
          errorContainer.textContent = 'Text exceeds maximum limit of 2,000 characters.';
          errorContainer.style.display = 'flex';
        }
        textarea.focus();
        return;
      }

      if (!window.CyAwareAPI || typeof window.CyAwareAPI.submitTextAnalysis !== 'function') {
        if (errorContainer) {
          errorContainer.textContent = 'API service unavailable. Please check your configuration.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      const saveOptIn = Boolean(saveCheckbox && saveCheckbox.checked);

      // Loading state
      const originalBtnHtml = submitBtn ? submitBtn.innerHTML : 'Analyze Text';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner" style="margin-right: 0.5rem;"></span> Analyzing Text...';
      }
      if (errorContainer) errorContainer.style.display = 'none';

      try {
        const res = await window.CyAwareAPI.submitTextAnalysis(text, saveOptIn);

        if (res && res.success && res.data) {
          renderTextAnalysisResult(res.data, statusContainer);
          if (window.CyAwareApp && window.CyAwareApp.showToast) {
            window.CyAwareApp.showToast('Analysis completed successfully.', 'success');
          }
        } else {
          throw new Error((res && res.message) || 'Analysis failed to return valid data.');
        }
      } catch (err) {
        console.warn('Text analysis error:', err.code, err.message);
        let errorMsg = err.message || 'An error occurred during text analysis.';

        if (err.code === 'UNAUTHENTICATED' || err.status === 401) {
          errorMsg = 'Saving analysis requires an active user session. Please sign in or uncheck save.';
        } else if (err.code === 'TEXT_TOO_LONG' || err.status === 413) {
          errorMsg = 'Text exceeds the backend limit of 2,000 characters.';
        } else if (err.code === 'EMPTY_TEXT') {
          errorMsg = 'Text cannot be empty.';
        }

        if (errorContainer) {
          errorContainer.textContent = errorMsg;
          errorContainer.style.display = 'flex';
        }
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast(errorMsg, 'danger');
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHtml;
        }
      }
    });

    updateCounters();
  }

  function renderTextAnalysisResult(data, container) {
    if (!container) return;

    const category = data.category || 'Normal';
    const confidencePct = data.confidence != null ? (Number(data.confidence) * 100).toFixed(1) + '%' : 'N/A';
    const badgeClass = getCategoryBadgeClass(category);
    const highlightedTerms = Array.isArray(data.highlighted_terms) ? data.highlighted_terms : [];
    const explanation = data.explanation || 'No detailed explanation provided.';
    const recommendation = data.safety_recommendation || '';
    const rewrite = data.safer_rewrite || '';
    const savedId = data.saved_id;

    let highlightedHtml = '';
    if (highlightedTerms.length > 0) {
      highlightedHtml = `
        <div style="margin-top: 0.75rem;">
          <span style="font-size: 0.82rem; font-weight: 600; color: var(--color-text-dim);">Highlighted Terms:</span>
          <div style="display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.25rem;">
            ${highlightedTerms.map(t => `<span class="badge" style="background: rgba(239, 68, 68, 0.15); color: #f87171; border-color: rgba(239, 68, 68, 0.3); font-size: 0.75rem;">${escapeHtml(t)}</span>`).join('')}
          </div>
        </div>
      `;
    }

    let rewriteHtml = '';
    if (rewrite) {
      rewriteHtml = `
        <div style="margin-top: 1rem; padding: 0.75rem 1rem; background: rgba(16, 185, 129, 0.08); border-left: 3px solid #10b981; border-radius: var(--radius-sm);">
          <div style="font-size: 0.82rem; font-weight: 700; color: #10b981; margin-bottom: 0.25rem;">Constructive Alternative Suggestion</div>
          <p style="margin: 0; font-size: 0.88rem; color: var(--color-text-main); font-style: italic;">"${escapeHtml(rewrite)}"</p>
        </div>
      `;
    }

    let savedNotice = '';
    if (savedId) {
      savedNotice = `
        <div class="badge badge-normal" style="font-size: 0.75rem; margin-left: 0.5rem;">
          Saved to History (ID: #${savedId})
        </div>
      `;
    }

    container.style.display = 'block';
    container.innerHTML = `
      <div class="card" style="margin-top: 1.5rem; border-top: 3px solid var(--color-primary);">
        <div class="flex justify-between items-center" style="margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span class="badge ${badgeClass}" style="font-size: 0.95rem; padding: 0.35rem 0.75rem;">
              ${escapeHtml(category)}
            </span>
            ${savedNotice}
          </div>
          <div style="text-align: right;">
            <span style="font-size: 0.82rem; color: var(--color-text-dim);">Model Confidence:</span>
            <strong style="font-size: 1rem; color: var(--color-text-main); margin-left: 0.25rem;">${confidencePct}</strong>
          </div>
        </div>

        <div style="margin-bottom: 1rem;">
          <div style="font-size: 0.85rem; font-weight: 600; color: var(--color-text-dim); margin-bottom: 0.25rem;">Analysis Explanation:</div>
          <p style="margin: 0; font-size: 0.92rem; color: var(--color-text-main); line-height: 1.5;">${escapeHtml(explanation)}</p>
          ${highlightedHtml}
        </div>

        ${recommendation ? `
          <div style="margin-top: 0.75rem; font-size: 0.88rem; color: var(--color-text-muted);">
            <strong>Safety Recommendation:</strong> ${escapeHtml(recommendation)}
          </div>
        ` : ''}

        ${rewriteHtml}

        <div class="alert alert-responsible-ai" style="margin-top: 1.25rem; margin-bottom: 0;">
          <div class="alert-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          </div>
          <div class="alert-content">
            <div class="alert-title">Responsible AI Confidence Advisory</div>
            <p style="margin: 0; font-size: 0.82rem;">
              Confidence scores represent uncalibrated decision probabilities output by the model and should not be interpreted as absolute guarantees. Classification assists human review and is not definitive proof of cyberbullying.
            </p>
          </div>
        </div>
      </div>
    `;

    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // ==========================================================================
  // 2. Document File Batch Analysis Controller
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

      const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
      if (ext !== '.csv' && ext !== '.txt') {
        if (errorContainer) {
          errorContainer.textContent = 'Only .csv and .txt document files are supported.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      if (file.size > 2 * 1024 * 1024) {
        if (errorContainer) {
          errorContainer.textContent = 'File exceeds maximum allowed size of 2 MB.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      selectedFile = file;
      if (fileNameEl) fileNameEl.textContent = file.name;
      if (fileSizeEl) fileSizeEl.textContent = (file.size / 1024).toFixed(1) + ' KB';

      if (fileCard) fileCard.style.display = 'flex';
      if (dropzone) dropzone.style.display = 'none';
      if (errorContainer) errorContainer.style.display = 'none';
      if (statusContainer) {
        statusContainer.style.display = 'none';
        statusContainer.innerHTML = '';
      }

      if (window.CyAwareApp && window.CyAwareApp.showToast) {
        window.CyAwareApp.showToast(`Selected: ${file.name}`, 'info');
      }
    }

    function clearFile() {
      selectedFile = null;
      fileInput.value = '';
      if (fileCard) fileCard.style.display = 'none';
      if (dropzone) dropzone.style.display = 'block';
      if (statusContainer) {
        statusContainer.style.display = 'none';
        statusContainer.innerHTML = '';
      }
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
    form.addEventListener('submit', async function (e) {
      e.preventDefault();

      if (!selectedFile) {
        if (errorContainer) {
          errorContainer.textContent = 'Please select a document file (.csv or .txt) to analyze.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      if (!window.CyAwareAPI || typeof window.CyAwareAPI.submitFileAnalysis !== 'function') {
        if (errorContainer) {
          errorContainer.textContent = 'API service unavailable. Please check your configuration.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      const originalBtnHtml = submitBtn ? submitBtn.innerHTML : 'Analyze Document File';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner" style="margin-right: 0.5rem;"></span> Uploading & Processing File...';
      }
      if (errorContainer) errorContainer.style.display = 'none';

      try {
        const res = await window.CyAwareAPI.submitFileAnalysis(selectedFile);

        if (res && res.success && res.data) {
          renderFileAnalysisResult(res.data, statusContainer);
          if (window.CyAwareApp && window.CyAwareApp.showToast) {
            window.CyAwareApp.showToast(`Batch processed: ${res.data.total_processed} items.`, 'success');
          }
        } else {
          throw new Error((res && res.message) || 'File analysis failed to return valid data.');
        }
      } catch (err) {
        console.warn('File analysis error:', err.code, err.message);
        let errorMsg = err.message || 'An error occurred during file batch analysis.';

        if (err.code === 'UNAUTHENTICATED' || err.status === 401) {
          errorMsg = 'Authentication required for file batch analysis. Please sign in to your account.';
        } else if (err.code === 'INVALID_FILE_TYPE' || err.status === 415) {
          errorMsg = 'Unsupported file format. Please upload a .csv or .txt document.';
        } else if (err.code === 'FILE_TOO_LARGE') {
          errorMsg = 'File exceeds maximum upload size limit of 2 MB.';
        } else if (err.code === 'ROW_LIMIT_EXCEEDED') {
          errorMsg = 'File exceeds maximum batch limit of 500 rows.';
        }

        if (errorContainer) {
          errorContainer.textContent = errorMsg;
          errorContainer.style.display = 'flex';
        }
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast(errorMsg, 'danger');
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHtml;
        }
      }
    });
  }

  function renderFileAnalysisResult(data, container) {
    if (!container) return;

    const total = data.total_processed || 0;
    const summary = data.category_summary || {};
    const rows = Array.isArray(data.results) ? data.results : [];

    const summaryPills = Object.keys(summary).map(cat => {
      const count = summary[cat] || 0;
      const badgeCls = getCategoryBadgeClass(cat);
      return `
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.5rem 0.75rem; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm);">
          <span class="badge ${badgeCls}" style="font-size: 0.78rem;">${escapeHtml(cat)}</span>
          <strong style="font-size: 0.9rem; color: var(--color-text-main); margin-left: 0.5rem;">${count}</strong>
        </div>
      `;
    }).join('');

    const tableRows = rows.slice(0, 100).map(r => {
      const catBadge = getCategoryBadgeClass(r.category);
      const confStr = r.confidence != null ? (Number(r.confidence) * 100).toFixed(1) + '%' : 'N/A';
      return `
        <tr>
          <td style="font-family: var(--font-family-mono); font-size: 0.8rem; color: var(--color-text-dim);">#${r.index}</td>
          <td style="font-size: 0.85rem; max-width: 320px; word-break: break-word;">${escapeHtml(r.text)}</td>
          <td><span class="badge ${catBadge}" style="font-size: 0.75rem;">${escapeHtml(r.category)}</span></td>
          <td style="font-size: 0.85rem; font-family: var(--font-family-mono); text-align: right;">${confStr}</td>
        </tr>
      `;
    }).join('');

    container.style.display = 'block';
    container.innerHTML = `
      <div class="card" style="margin-top: 1.5rem; border-top: 3px solid var(--color-primary);">
        <div class="flex justify-between items-center" style="margin-bottom: 1rem;">
          <div>
            <h4 style="margin: 0; font-size: 1.05rem;">Batch Analysis Completed</h4>
            <span style="font-size: 0.82rem; color: var(--color-text-dim);">File: ${escapeHtml(data.filename)} &bull; ${total} items processed</span>
          </div>
        </div>

        <div style="margin-bottom: 1.25rem;">
          <div style="font-size: 0.82rem; font-weight: 600; color: var(--color-text-dim); margin-bottom: 0.5rem;">Category Distribution Summary:</div>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.5rem;">
            ${summaryPills}
          </div>
        </div>

        <div style="margin-bottom: 1rem;">
          <div style="font-size: 0.82rem; font-weight: 600; color: var(--color-text-dim); margin-bottom: 0.5rem;">
            Evaluated Rows ${rows.length > 100 ? '(Showing first 100 items)' : ''}:
          </div>
          <div class="table-responsive" style="max-height: 320px; overflow-y: auto;">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 60px;">Row</th>
                  <th>Extracted Passage</th>
                  <th style="width: 130px;">Category</th>
                  <th style="width: 90px; text-align: right;">Confidence</th>
                </tr>
              </thead>
              <tbody>
                ${tableRows}
              </tbody>
            </table>
          </div>
        </div>

        <div class="alert alert-responsible-ai" style="margin-top: 1rem; margin-bottom: 0;">
          <div class="alert-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          </div>
          <div class="alert-content">
            <div class="alert-title">Responsible Document Review</div>
            <p style="margin: 0; font-size: 0.82rem;">
              Batch documents may contain varied conversational context. Isolated flagged lines should be reviewed by human moderators in context rather than triggering automated disciplinary action.
            </p>
          </div>
        </div>
      </div>
    `;

    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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

      const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
      if (ext !== '.png' && ext !== '.jpg' && ext !== '.jpeg') {
        if (errorContainer) {
          errorContainer.textContent = 'Unsupported image format. Only PNG, JPG, and JPEG images are allowed.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      if (file.size > 5 * 1024 * 1024) {
        if (errorContainer) {
          errorContainer.textContent = 'Image exceeds maximum size limit of 5 MB.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      selectedImage = file;
      if (imageNameEl) imageNameEl.textContent = file.name;
      if (imageSizeEl) imageSizeEl.textContent = (file.size / 1024).toFixed(1) + ' KB';

      const reader = new FileReader();
      reader.onload = function (e) {
        if (previewImg) previewImg.src = e.target.result;
        if (previewContainer) previewContainer.style.display = 'block';
        if (dropzone) dropzone.style.display = 'none';
        if (errorContainer) errorContainer.style.display = 'none';
        if (statusContainer) {
          statusContainer.style.display = 'none';
          statusContainer.innerHTML = '';
        }
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
      if (statusContainer) {
        statusContainer.style.display = 'none';
        statusContainer.innerHTML = '';
      }
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

    // Form Submission: Extracts OCR text
    form.addEventListener('submit', async function (e) {
      e.preventDefault();

      if (!selectedImage) {
        if (errorContainer) {
          errorContainer.textContent = 'Please select a chat screenshot or image to analyze.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      if (!window.CyAwareAPI || typeof window.CyAwareAPI.submitImageAnalysis !== 'function') {
        if (errorContainer) {
          errorContainer.textContent = 'API service unavailable. Please check your configuration.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      const originalBtnHtml = submitBtn ? submitBtn.innerHTML : 'Analyze Screenshot OCR';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner" style="margin-right: 0.5rem;"></span> Extracting Text via OCR...';
      }
      if (errorContainer) errorContainer.style.display = 'none';

      try {
        const res = await window.CyAwareAPI.submitImageAnalysis(selectedImage);

        if (res && res.success && res.data) {
          renderOcrExtractionResult(res.data, statusContainer);
          if (window.CyAwareApp && window.CyAwareApp.showToast) {
            window.CyAwareApp.showToast('Text extracted from screenshot successfully.', 'success');
          }
        } else {
          throw new Error((res && res.message) || 'Image OCR failed to return valid text data.');
        }
      } catch (err) {
        console.warn('Image OCR error:', err.code, err.message);
        let errorMsg = err.message || 'An error occurred during OCR text extraction.';

        if (err.code === 'OCR_ENGINE_NOT_AVAILABLE' || err.status === 503) {
          errorMsg = 'Server-side OCR engine (Tesseract) is unavailable on the host system. Please transcribe or paste text directly into Single Text Analysis.';
        } else if (err.code === 'UNAUTHENTICATED' || err.status === 401) {
          errorMsg = 'Authentication required for screenshot OCR analysis. Please sign in to your account.';
        } else if (err.code === 'INVALID_IMAGE_TYPE' || err.status === 415) {
          errorMsg = 'Unsupported image format. Only PNG, JPG, and JPEG images are allowed.';
        } else if (err.code === 'IMAGE_TOO_LARGE') {
          errorMsg = 'Image exceeds maximum size limit of 5 MB.';
        }

        if (errorContainer) {
          errorContainer.textContent = errorMsg;
          errorContainer.style.display = 'flex';
        }
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast(errorMsg, 'danger');
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHtml;
        }
      }
    });
  }

  function renderOcrExtractionResult(data, container) {
    if (!container) return;

    const extractedText = data.extracted_text || '';
    const ocrConfidence = data.ocr_confidence != null ? data.ocr_confidence : 0;
    const lineCount = data.line_count || 0;
    const wordCount = data.word_count || 0;

    container.style.display = 'block';
    container.innerHTML = `
      <div class="card" style="margin-top: 1.5rem; border-top: 3px solid var(--color-primary);">
        <div class="flex justify-between items-center" style="margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
          <div>
            <h4 style="margin: 0; font-size: 1.05rem; display: flex; align-items: center; gap: 0.5rem;">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
              OCR Text Extraction Complete
            </h4>
            <span style="font-size: 0.82rem; color: var(--color-text-dim);">
              Extracted: ${lineCount} lines &bull; ${wordCount} words
            </span>
          </div>
          <div>
            <span style="font-size: 0.82rem; color: var(--color-text-dim);">OCR Extraction Confidence:</span>
            <span class="badge" style="background: rgba(0, 210, 255, 0.15); color: var(--color-primary); font-weight: 700; margin-left: 0.35rem;">
              ${ocrConfidence}%
            </span>
          </div>
        </div>

        <div style="margin-bottom: 1rem;">
          <label for="ocr-extracted-text" class="form-label" style="font-size: 0.88rem; font-weight: 600;">
            Review and Edit Extracted Text:
          </label>
          <div style="font-size: 0.8rem; color: var(--color-text-dim); margin-bottom: 0.5rem;">
            OCR transcriptions may misread symbols or low-resolution characters. Please review or correct the text before initiating NLP classification.
          </div>
          <textarea id="ocr-extracted-text" class="textarea-control" rows="6" style="font-size: 0.92rem;">${escapeHtml(extractedText)}</textarea>
          <div id="ocr-nlp-error" class="invalid-feedback" style="display: none; margin-top: 0.5rem;"></div>
        </div>

        <div class="flex justify-between items-center">
          <span style="font-size: 0.8rem; color: var(--color-text-dim);">Screenshots are not saved to server storage by default.</span>
          <button type="button" id="btn-analyze-extracted-text" class="btn btn-primary btn-md">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            Analyze Extracted Text
          </button>
        </div>

        <div id="ocr-classification-status" style="margin-top: 1.25rem;"></div>
      </div>
    `;

    const analyzeExtractedBtn = document.getElementById('btn-analyze-extracted-text');
    const ocrTextarea = document.getElementById('ocr-extracted-text');
    const ocrNlpError = document.getElementById('ocr-nlp-error');
    const ocrClassStatus = document.getElementById('ocr-classification-status');

    if (analyzeExtractedBtn && ocrTextarea) {
      analyzeExtractedBtn.addEventListener('click', async function () {
        const textToAnalyze = ocrTextarea.value.trim();

        if (!textToAnalyze) {
          if (ocrNlpError) {
            ocrNlpError.textContent = 'Extracted text cannot be empty. Please verify the transcription.';
            ocrNlpError.style.display = 'flex';
          }
          ocrTextarea.focus();
          return;
        }

        if (ocrNlpError) ocrNlpError.style.display = 'none';

        const originalHtml = analyzeExtractedBtn.innerHTML;
        analyzeExtractedBtn.disabled = true;
        analyzeExtractedBtn.innerHTML = '<span class="spinner" style="margin-right: 0.5rem;"></span> Evaluating Safety...';

        try {
          // Do not save screenshot transcriptions by default
          const result = await window.CyAwareAPI.submitTextAnalysis(textToAnalyze, false);

          if (result && result.success && result.data) {
            renderTextAnalysisResult(result.data, ocrClassStatus);
            if (window.CyAwareApp && window.CyAwareApp.showToast) {
              window.CyAwareApp.showToast('OCR extracted text classified successfully.', 'success');
            }
          } else {
            throw new Error((result && result.message) || 'Classification failed.');
          }
        } catch (err) {
          console.warn('OCR NLP classification error:', err);
          if (ocrNlpError) {
            ocrNlpError.textContent = err.message || 'Failed to classify extracted text.';
            ocrNlpError.style.display = 'flex';
          }
        } finally {
          analyzeExtractedBtn.disabled = false;
          analyzeExtractedBtn.innerHTML = originalHtml;
        }
      });
    }

    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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

    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        conversationMessages = [];
        renderConversation();
        if (statusContainer) {
          statusContainer.style.display = 'none';
          statusContainer.innerHTML = '';
        }
        if (errorContainer) errorContainer.style.display = 'none';
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast('Conversation thread cleared.', 'info');
        }
      });
    }

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

    // Form Submission: Ephemeral multi-turn analysis
    form.addEventListener('submit', async function (e) {
      e.preventDefault();

      if (conversationMessages.length < 2) {
        if (errorContainer) {
          errorContainer.textContent = 'Conversation requires at least 2 messages for multi-turn analysis.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      if (conversationMessages.length > 50) {
        if (errorContainer) {
          errorContainer.textContent = 'Conversation exceeds maximum limit of 50 messages.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      if (!window.CyAwareAPI || typeof window.CyAwareAPI.submitConversationAnalysis !== 'function') {
        if (errorContainer) {
          errorContainer.textContent = 'API service unavailable. Please check your configuration.';
          errorContainer.style.display = 'flex';
        }
        return;
      }

      // Map to exact backend format: { text, speaker }
      const formattedMessages = conversationMessages.map(msg => ({
        speaker: msg.sender || 'Participant',
        text: msg.message
      }));

      const originalBtnHtml = submitBtn ? submitBtn.innerHTML : 'Analyze Conversation Thread';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner" style="margin-right: 0.5rem;"></span> Evaluating Contextual Flow...';
      }
      if (errorContainer) errorContainer.style.display = 'none';

      try {
        const res = await window.CyAwareAPI.submitConversationAnalysis(formattedMessages);

        if (res && res.success && res.data) {
          renderConversationAnalysisResult(res.data, statusContainer);
          if (window.CyAwareApp && window.CyAwareApp.showToast) {
            window.CyAwareApp.showToast('Conversation sequence analyzed.', 'success');
          }
        } else {
          throw new Error((res && res.message) || 'Conversation analysis failed.');
        }
      } catch (err) {
        console.warn('Conversation analysis error:', err.code, err.message);
        let errorMsg = err.message || 'An error occurred during conversation analysis.';

        if (err.code === 'UNAUTHENTICATED' || err.status === 401) {
          errorMsg = 'Authentication required for conversation thread analysis. Please sign in to your account.';
        } else if (err.code === 'INVALID_CONVERSATION') {
          errorMsg = 'Conversation requires between 2 and 50 messages.';
        }

        if (errorContainer) {
          errorContainer.textContent = errorMsg;
          errorContainer.style.display = 'flex';
        }
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast(errorMsg, 'danger');
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHtml;
        }
      }
    });

    renderConversation();
  }

  function renderConversationAnalysisResult(data, container) {
    if (!container) return;

    // Render ONLY supported fields from actual backend response
    const indicators = data.conversation_indicators || {};
    const totalMessages = indicators.total_messages || 0;
    const flaggedCount = indicators.flagged_message_count || 0;
    const repeatedHarm = Boolean(indicators.repeated_harm_indicator);
    const patternSummary = indicators.pattern_summary || 'No pattern summary available.';
    const evaluations = Array.isArray(data.message_evaluations) ? data.message_evaluations : [];

    const turnsHtml = evaluations.map(ev => {
      const badgeCls = getCategoryBadgeClass(ev.category);
      const confStr = ev.confidence != null ? (Number(ev.confidence) * 100).toFixed(1) + '%' : 'N/A';
      return `
        <div style="padding: 0.75rem 1rem; border-bottom: 1px solid var(--color-border-subtle); display: flex; justify-content: space-between; align-items: center; gap: 1rem;">
          <div>
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
              <span style="font-weight: 700; font-size: 0.88rem; color: var(--color-text-main);">${escapeHtml(ev.speaker)}</span>
              <span style="font-size: 0.75rem; color: var(--color-text-dim);">Turn #${ev.index + 1}</span>
            </div>
            ${ev.highlighted_terms && ev.highlighted_terms.length > 0 ? `
              <div style="font-size: 0.78rem; color: #f87171;">
                Flagged terms: ${ev.highlighted_terms.map(t => escapeHtml(t)).join(', ')}
              </div>
            ` : ''}
          </div>
          <div style="text-align: right; white-space: nowrap;">
            <span class="badge ${badgeCls}" style="font-size: 0.75rem;">${escapeHtml(ev.category)}</span>
            <div style="font-size: 0.75rem; color: var(--color-text-dim); margin-top: 0.2rem;">${confStr}</div>
          </div>
        </div>
      `;
    }).join('');

    container.style.display = 'block';
    container.innerHTML = `
      <div class="card" style="margin-top: 1.5rem; border-top: 3px solid var(--color-primary);">
        <div class="flex justify-between items-center" style="margin-bottom: 1rem;">
          <h4 style="margin: 0; font-size: 1.05rem;">Conversation Context Analysis</h4>
          <span class="badge" style="background: rgba(148, 163, 184, 0.1); color: var(--color-text-dim); font-size: 0.75rem;">
            Ephemeral (Not Stored)
          </span>
        </div>

        <!-- Metrics Overview Grid -->
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; margin-bottom: 1.25rem;">
          <div style="padding: 0.75rem; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); text-align: center;">
            <div style="font-size: 0.75rem; color: var(--color-text-dim);">Total Messages</div>
            <div style="font-size: 1.25rem; font-weight: 800; color: var(--color-text-main); margin-top: 0.2rem;">${totalMessages}</div>
          </div>
          <div style="padding: 0.75rem; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); text-align: center;">
            <div style="font-size: 0.75rem; color: var(--color-text-dim);">Flagged Turns</div>
            <div style="font-size: 1.25rem; font-weight: 800; color: ${flaggedCount > 0 ? '#ef4444' : '#10b981'}; margin-top: 0.2rem;">${flaggedCount}</div>
          </div>
          <div style="padding: 0.75rem; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); text-align: center;">
            <div style="font-size: 0.75rem; color: var(--color-text-dim);">Repeated Harm Indicator</div>
            <div style="font-size: 1rem; font-weight: 700; color: ${repeatedHarm ? '#ef4444' : '#10b981'}; margin-top: 0.35rem;">
              ${repeatedHarm ? 'Observed Pattern' : 'None Detected'}
            </div>
          </div>
        </div>

        <!-- Pattern Summary -->
        <div style="margin-bottom: 1.25rem; padding: 0.85rem 1rem; background: rgba(0, 210, 255, 0.05); border-left: 3px solid var(--color-primary); border-radius: var(--radius-sm);">
          <div style="font-size: 0.82rem; font-weight: 700; color: var(--color-primary); margin-bottom: 0.25rem;">Contextual Pattern Summary</div>
          <p style="margin: 0; font-size: 0.88rem; color: var(--color-text-main); line-height: 1.5;">${escapeHtml(patternSummary)}</p>
        </div>

        <!-- Message Turns Breakdown -->
        <div style="margin-bottom: 1rem;">
          <div style="font-size: 0.82rem; font-weight: 600; color: var(--color-text-dim); margin-bottom: 0.5rem;">Turn-by-Turn Evaluations:</div>
          <div style="background: rgba(0, 0, 0, 0.15); border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); max-height: 280px; overflow-y: auto;">
            ${turnsHtml}
          </div>
        </div>

        <div class="alert alert-responsible-ai" style="margin-top: 1rem; margin-bottom: 0;">
          <div class="alert-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          </div>
          <div class="alert-content">
            <div class="alert-title">Responsible Relational Context Notice</div>
            <p style="margin: 0; font-size: 0.82rem;">
              Dialogue patterns provide assistive signals for human moderators. Under no circumstances does automated evaluation label participants as bullies or victims.
            </p>
          </div>
        </div>
      </div>
    `;

    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // Initialize all controllers on DOM ready
  document.addEventListener('DOMContentLoaded', function () {
    initTextAnalysis();
    initFileAnalysis();
    initImageAnalysis();
    initConversationAnalysis();
  });
})();
