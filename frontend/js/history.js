/**
 * CyAware — Analysis History Controller
 * File: frontend/js/history.js
 * 
 * Controls the Analysis History & Audit Log page.
 * Targets GET /api/analyses and DELETE /api/analyses/{id}.
 * 
 * Strict Project Rules:
 * - Does not invent response schemas or pagination query parameters.
 * - Displays honest pending-backend demonstration states.
 * - Keeps record deletion disabled until backend requirements are confirmed.
 */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    initHistoryPage();
  });

  async function initHistoryPage() {
    const searchInput = document.getElementById('history-search');
    const categorySelect = document.getElementById('history-filter-category');
    const channelSelect = document.getElementById('history-filter-channel');
    const resetBtn = document.getElementById('history-filter-reset');
    const deleteModal = document.getElementById('delete-confirm-modal');
    const confirmDeleteBtn = document.getElementById('btn-confirm-delete');

    // Filter controls
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        if (searchInput) searchInput.value = '';
        if (categorySelect) categorySelect.value = '';
        if (channelSelect) channelSelect.value = '';
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast('Filters reset.', 'info');
        }
      });
    }

    // Keep deletion disabled with informative notice if clicked
    if (confirmDeleteBtn) {
      confirmDeleteBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast('Record deletion is disabled pending backend confirmation.', 'warning');
        }
      });
    }

    // Load history records from API client
    try {
      if (window.CyAwareAPI && window.CyAwareAPI.getAnalysesHistory) {
        const result = await window.CyAwareAPI.getAnalysesHistory();
        // Pending backend status: UI retains the empty/pending placeholder row
      }
    } catch (err) {
      console.warn('History initialization notice:', err.message);
      if (window.CyAwareApp && window.CyAwareApp.showToast) {
        window.CyAwareApp.showToast('History awaiting backend connection: ' + err.message, 'info');
      }
    }
  }

})();

