/**
 * CyAware — Analysis History Controller
 * File: frontend/js/history.js
 * 
 * Connects the Analysis History & Audit Log page to:
 * - GET /api/analyses (paginated, with category filtering)
 * - DELETE /api/analyses/{id} (individual record deletion with CSRF protection)
 * 
 * Strict Project Rules:
 * - Real backend records dictate all table rows, timestamps, and classifications.
 * - Does not send unsupported query parameters (e.g. channel) to GET /api/analyses.
 * - Handles the unsupported channel filter honestly with transparent user guidance.
 * - Requires explicit user confirmation before deleting records.
 * - Refreshes table upon successful deletion.
 * - Handles authentication expiry and empty history states gracefully.
 */

(function () {
  'use strict';

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

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

  document.addEventListener('DOMContentLoaded', function () {
    initHistoryPage();
  });

  async function initHistoryPage() {
    const searchInput = document.getElementById('history-search');
    const categorySelect = document.getElementById('history-filter-category');
    const channelSelect = document.getElementById('history-filter-channel');
    const resetBtn = document.getElementById('history-filter-reset');
    const tbody = document.getElementById('history-tbody');
    const paginationInfo = document.getElementById('pagination-info');
    const prevBtn = document.getElementById('pagination-prev');
    const nextBtn = document.getElementById('pagination-next');
    const deleteModal = document.getElementById('delete-confirm-modal');
    const confirmDeleteBtn = document.getElementById('btn-confirm-delete');

    let currentPage = 1;
    const limit = 10;
    let totalPages = 1;
    let totalRecords = 0;
    let pendingDeleteId = null;
    let currentRecords = [];

    // Check API client availability
    if (!window.CyAwareAPI || typeof window.CyAwareAPI.getAnalysesHistory !== 'function') {
      renderErrorMessage('The CyAware API client is not loaded. Please verify application scripts.');
      return;
    }

    // Modal close controls
    function closeModal() {
      if (deleteModal) {
        deleteModal.classList.remove('active');
        deleteModal.setAttribute('aria-hidden', 'true');
      }
      pendingDeleteId = null;
      if (confirmDeleteBtn) {
        confirmDeleteBtn.disabled = true;
      }
    }

    function openModal(id) {
      pendingDeleteId = id;
      if (deleteModal) {
        deleteModal.classList.add('active');
        deleteModal.setAttribute('aria-hidden', 'false');
      }
      if (confirmDeleteBtn) {
        confirmDeleteBtn.disabled = false;
        confirmDeleteBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          Delete Record #${id}
        `;
      }
    }

    if (deleteModal) {
      deleteModal.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', closeModal);
      });
      deleteModal.addEventListener('click', function (e) {
        if (e.target === deleteModal) closeModal();
      });
    }

    // Modal Deletion Confirmation
    if (confirmDeleteBtn) {
      confirmDeleteBtn.addEventListener('click', async function () {
        if (!pendingDeleteId) return;

        confirmDeleteBtn.disabled = true;
        confirmDeleteBtn.innerHTML = '<span class="spinner" style="margin-right: 0.4rem;"></span> Deleting...';

        try {
          const res = await window.CyAwareAPI.deleteAnalysis(pendingDeleteId);

          if (res && res.success) {
            closeModal();
            if (window.CyAwareApp && window.CyAwareApp.showToast) {
              window.CyAwareApp.showToast(`Analysis record #${pendingDeleteId} deleted successfully.`, 'success');
            }
            // Reload current page records
            loadHistory();
          } else {
            throw new Error((res && res.message) || 'Failed to delete record.');
          }
        } catch (err) {
          console.warn('Deletion error:', err.code, err.message);
          let userMsg = err.message || 'Failed to delete analysis record.';
          if (err.code === 'ANALYSIS_NOT_FOUND' || err.status === 404) {
            userMsg = 'Analysis record not found or already deleted.';
          } else if (err.code === 'CSRF_ERROR' || err.status === 403) {
            userMsg = 'Security validation failed (CSRF token missing or expired). Please refresh.';
          }
          if (window.CyAwareApp && window.CyAwareApp.showToast) {
            window.CyAwareApp.showToast(userMsg, 'danger');
          }
          closeModal();
        }
      });
    }

    // Load History from Backend API
    async function loadHistory() {
      renderLoading();

      const params = {
        page: currentPage,
        limit: limit
      };

      // Category filter (supported by backend)
      const selectedCategory = categorySelect ? categorySelect.value.trim() : '';
      if (selectedCategory) {
        params.category = selectedCategory;
      }

      // Channel filter handling:
      // Backend does not support channel filter on GET /api/analyses.
      // We do not send unsupported query parameters to backend.
      const selectedChannel = channelSelect ? channelSelect.value.trim() : '';
      if (selectedChannel && selectedChannel !== 'text') {
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast('Note: Only text analyses are persisted in history. Files, images, and conversations are not stored as individual history records.', 'info');
        }
      }

      try {
        const response = await window.CyAwareAPI.getAnalysesHistory(params);

        if (response && response.success && response.data) {
          const pagination = response.data.pagination || {};
          currentRecords = Array.isArray(response.data.items) ? response.data.items : [];
          totalRecords = Number(pagination.total) || 0;
          totalPages = Number(pagination.total_pages) || 0;
          currentPage = Number(pagination.page) || 1;

          renderTable(filterRecordsBySearch(currentRecords));
          updatePaginationControls();
        } else {
          throw new Error((response && response.message) || 'Failed to load historical analyses.');
        }
      } catch (err) {
        console.warn('History fetch error:', err.code, err.message);

        if (err.status === 401 || err.code === 'UNAUTHENTICATED') {
          renderUnauthenticated();
          return;
        }

        renderErrorMessage(err.message || 'Error communicating with backend service.');
      }
    }

    // Client-side search filtering across text content or ID on the current page
    function filterRecordsBySearch(records) {
      const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
      if (!query) return records;

      return records.filter(item => {
        const idMatch = String(item.id).includes(query);
        const textMatch = item.text_content && item.text_content.toLowerCase().includes(query);
        return idMatch || textMatch;
      });
    }

    // Render Table Rows
    function renderTable(records) {
      if (!tbody) return;

      if (!records || records.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="5" class="data-table-empty">
              <div style="width: 44px; height: 44px; border-radius: 50%; background: rgba(0, 210, 255, 0.1); color: var(--color-primary); display: flex; align-items: center; justify-content: center; margin: 0 auto 0.75rem auto;">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              </div>
              <div style="font-weight: 700; font-size: 1.05rem; margin-bottom: 0.35rem; color: var(--color-text-main);">
                No Matching Analyses Found
              </div>
              <p style="font-size: 0.85rem; color: var(--color-text-dim); max-width: 520px; margin: 0 auto 1rem auto;">
                ${totalRecords === 0 ? 'You have not saved any analyses yet. Run a single text analysis and choose "Save to history".' : 'No records on this page match your current search query or filter.'}
              </p>
              ${totalRecords === 0 ? '<a href="analyze-text.html" class="btn btn-primary btn-sm">Run Text Analysis</a>' : ''}
            </td>
          </tr>
        `;
        return;
      }

      const rowsHtml = records.map(item => {
        const badgeCls = getCategoryBadgeClass(item.category);
        const confStr = item.confidence != null ? (Number(item.confidence) * 100).toFixed(1) + '%' : 'N/A';
        const dateStr = item.saved_at ? new Date(item.saved_at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }) : '';
        const preview = item.text_content ? (item.text_content.length > 70 ? item.text_content.substring(0, 70) + '...' : item.text_content) : '—';

        return `
          <tr>
            <td style="font-family: var(--font-family-mono); font-size: 0.85rem; font-weight: 600; color: var(--color-primary);">
              #${item.id}
            </td>
            <td>
              <span class="badge" style="background: rgba(0, 210, 255, 0.1); color: var(--color-primary); font-size: 0.72rem;">
                Single Text
              </span>
            </td>
            <td>
              <div style="font-size: 0.88rem; color: var(--color-text-main); line-height: 1.4; word-break: break-word;">
                "${escapeHtml(preview)}"
              </div>
              <div style="font-size: 0.75rem; color: var(--color-text-dim); margin-top: 0.2rem;">
                Saved on ${escapeHtml(dateStr)}
              </div>
            </td>
            <td>
              <div style="display: flex; align-items: center; gap: 0.35rem;">
                <span class="badge ${badgeCls}" style="font-size: 0.75rem;">${escapeHtml(item.category)}</span>
                <span style="font-size: 0.78rem; font-family: var(--font-family-mono); color: var(--color-text-dim);">${confStr}</span>
              </div>
            </td>
            <td style="text-align: right;">
              <button type="button" class="btn btn-ghost btn-sm btn-delete-row" data-id="${item.id}" title="Delete Record #${item.id}" style="color: #ef4444;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 0.2rem;"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                Delete
              </button>
            </td>
          </tr>
        `;
      }).join('');

      tbody.innerHTML = rowsHtml;

      // Attach delete click listeners
      tbody.querySelectorAll('.btn-delete-row').forEach(btn => {
        btn.addEventListener('click', function () {
          const id = parseInt(this.getAttribute('data-id'), 10);
          openModal(id);
        });
      });
    }

    function renderLoading() {
      if (!tbody) return;
      tbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; padding: 2.5rem; color: var(--color-text-dim);">
            <span class="spinner" style="margin-right: 0.5rem;"></span> Loading analysis records...
          </td>
        </tr>
      `;
    }

    function renderUnauthenticated() {
      if (!tbody) return;
      tbody.innerHTML = `
        <tr>
          <td colspan="5" class="data-table-empty">
            <div style="width: 44px; height: 44px; border-radius: 50%; background: rgba(245, 158, 11, 0.1); color: #f59e0b; display: flex; align-items: center; justify-content: center; margin: 0 auto 0.75rem auto;">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            </div>
            <div style="font-weight: 700; font-size: 1.05rem; margin-bottom: 0.35rem; color: var(--color-text-main);">
              Authentication Required
            </div>
            <p style="font-size: 0.85rem; color: var(--color-text-dim); max-width: 480px; margin: 0 auto 1rem auto;">
              Your session has expired or you are not signed in. Please log in to view and manage your analysis history.
            </p>
            <a href="login.html" class="btn btn-primary btn-sm">Sign In</a>
          </td>
        </tr>
      `;
      if (paginationInfo) paginationInfo.textContent = '0 records';
      if (prevBtn) prevBtn.disabled = true;
      if (nextBtn) nextBtn.disabled = true;
    }

    function renderErrorMessage(msg) {
      if (!tbody) return;
      tbody.innerHTML = `
        <tr>
          <td colspan="5" class="data-table-empty">
            <div style="font-weight: 700; font-size: 1rem; color: #ef4444; margin-bottom: 0.25rem;">
              Failed to Load History
            </div>
            <p style="font-size: 0.85rem; color: var(--color-text-dim); margin: 0;">${escapeHtml(msg)}</p>
          </td>
        </tr>
      `;
    }

    function updatePaginationControls() {
      if (paginationInfo) {
        paginationInfo.textContent = `${totalRecords} record${totalRecords === 1 ? '' : 's'} (Page ${currentPage} of ${totalPages || 1})`;
      }
      if (prevBtn) {
        prevBtn.disabled = currentPage <= 1;
      }
      if (nextBtn) {
        nextBtn.disabled = currentPage >= totalPages || totalPages === 0;
      }
    }

    // Pagination events
    if (prevBtn) {
      prevBtn.addEventListener('click', function () {
        if (currentPage > 1) {
          currentPage--;
          loadHistory();
        }
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', function () {
        if (currentPage < totalPages) {
          currentPage++;
          loadHistory();
        }
      });
    }

    // Filter events
    if (categorySelect) {
      categorySelect.addEventListener('change', function () {
        currentPage = 1;
        loadHistory();
      });
    }

    if (channelSelect) {
      channelSelect.addEventListener('change', function () {
        const val = this.value;
        if (val && val !== 'text') {
          if (window.CyAwareApp && window.CyAwareApp.showToast) {
            window.CyAwareApp.showToast('File, image, and conversation analyses are ephemeral and not saved to audit history.', 'info');
          }
        }
      });
    }

    if (searchInput) {
      searchInput.addEventListener('input', function () {
        renderTable(filterRecordsBySearch(currentRecords));
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        if (searchInput) searchInput.value = '';
        if (categorySelect) categorySelect.value = '';
        if (channelSelect) channelSelect.value = '';
        currentPage = 1;
        loadHistory();
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast('Filters reset.', 'info');
        }
      });
    }

    // Initial load
    loadHistory();
  }
})();
