/**
 * CyAware — User Settings & Privacy Controller
 * File: frontend/js/settings.js
 * 
 * Manages user profile display, GDPR/CCPA data export, and account deletion
 * strictly using window.CyAwareAPI (getMe, exportUserData, deleteAccount).
 * 
 * Strict Project Rules:
 * - Uses only confirmed backend endpoints and response structures.
 * - Handles loading, unauthenticated, and error states gracefully.
 * - Requires explicit user confirmation prior to account deletion.
 * - Disables double-submission during export and deletion actions.
 * - Never fabricates fake profile fields or status messages.
 */

(function () {
  'use strict';

  let currentUser = null;

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function showToast(message, type = 'info', duration = 4000) {
    if (window.CyAwareApp && typeof window.CyAwareApp.showToast === 'function') {
      window.CyAwareApp.showToast(message, type, duration);
    } else {
      console.log(`[Toast ${type}] ${message}`);
    }
  }

  function openModal(modalId) {
    if (window.CyAwareApp && typeof window.CyAwareApp.openModal === 'function') {
      window.CyAwareApp.openModal(modalId);
    } else {
      const modal = document.getElementById(modalId);
      if (modal) {
        modal.classList.add('active');
        modal.setAttribute('aria-hidden', 'false');
      }
    }
  }

  function closeModal(modalId) {
    if (window.CyAwareApp && typeof window.CyAwareApp.closeModal === 'function') {
      window.CyAwareApp.closeModal(modalId);
    } else {
      const modal = document.getElementById(modalId);
      if (modal) {
        modal.classList.remove('active');
        modal.setAttribute('aria-hidden', 'true');
      }
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    initSettingsController();
  });

  async function initSettingsController() {
    const usernameInput = document.getElementById('account-username');
    const emailInput = document.getElementById('account-email');
    const roleInput = document.getElementById('account-role');
    const statusBadge = document.getElementById('account-status-badge');
    const statusBanner = document.getElementById('account-status-banner');
    const btnExport = document.getElementById('btn-export-data');
    const btnDelete = document.getElementById('btn-delete-account');
    const btnConfirmDelete = document.getElementById('btn-confirm-delete-account');

    // 1. Verify CyAwareAPI client availability
    if (!window.CyAwareAPI || typeof window.CyAwareAPI.getMe !== 'function') {
      if (statusBadge) {
        statusBadge.className = 'badge badge-danger';
        statusBadge.textContent = 'API Unavailable';
      }
      if (statusBanner) {
        statusBanner.className = 'alert alert-danger';
        statusBanner.innerHTML = `
          <div class="alert-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
          <div class="alert-content">
            <div class="alert-title">API Client Unavailable</div>
            <p style="margin: 0; font-size: 0.88rem;">The CyAware API service is not loaded. Please verify script imports.</p>
          </div>
        `;
      }
      if (btnExport) btnExport.disabled = true;
      if (btnDelete) btnDelete.disabled = true;
      return;
    }

    // 2. Load User Profile
    await loadUserProfile();

    // 3. Attach Event Listeners
    if (btnExport) {
      btnExport.addEventListener('click', handleDataExport);
    }

    if (btnDelete) {
      btnDelete.addEventListener('click', function () {
        if (!currentUser) {
          showToast('You must be signed in to manage your account.', 'warning');
          return;
        }
        openModal('modal-delete-account-confirm');
      });
    }

    if (btnConfirmDelete) {
      btnConfirmDelete.addEventListener('click', handleAccountDeletion);
    }

    /**
     * Fetch and render authenticated user profile
     */
    async function loadUserProfile() {
      if (statusBadge) {
        statusBadge.className = 'badge badge-outline';
        statusBadge.textContent = 'Checking Session...';
      }

      try {
        const response = await window.CyAwareAPI.getMe();

        if (response && response.success && response.data && response.data.user) {
          currentUser = response.data.user;

          if (usernameInput) usernameInput.value = currentUser.username || '';
          if (emailInput) emailInput.value = currentUser.email || '';
          if (roleInput) roleInput.value = currentUser.role || 'user';

          if (statusBadge) {
            statusBadge.className = 'badge badge-success';
            statusBadge.textContent = 'Authenticated';
          }

          if (statusBanner) {
            statusBanner.innerHTML = '';
          }

          if (btnExport) btnExport.disabled = false;
          if (btnDelete) btnDelete.disabled = false;
        } else {
          handleUnauthenticated();
        }
      } catch (err) {
        if (err.status === 401 || err.code === 'UNAUTHENTICATED') {
          handleUnauthenticated();
        } else {
          handleProfileError(err);
        }
      }
    }

    /**
     * Handle unauthenticated guest visitor state
     */
    function handleUnauthenticated() {
      currentUser = null;

      if (usernameInput) usernameInput.value = 'Not signed in';
      if (emailInput) emailInput.value = 'Not signed in';
      if (roleInput) roleInput.value = 'Guest';

      if (statusBadge) {
        statusBadge.className = 'badge badge-warning';
        statusBadge.textContent = 'Guest Session';
      }

      if (statusBanner) {
        statusBanner.className = 'alert alert-warning';
        statusBanner.innerHTML = `
          <div class="alert-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          </div>
          <div class="alert-content">
            <div class="alert-title">Authentication Required</div>
            <p style="margin: 0; font-size: 0.88rem;">
              You are currently viewing settings as a guest. Please <a href="login.html" style="font-weight: 700; color: var(--color-primary); text-decoration: underline;">sign in</a> to view your profile, export personal data, or manage your account.
            </p>
          </div>
        `;
      }

      if (btnExport) {
        btnExport.disabled = true;
        btnExport.setAttribute('title', 'Sign in required to export data.');
      }
      if (btnDelete) {
        btnDelete.disabled = true;
        btnDelete.setAttribute('title', 'Sign in required to delete account.');
      }
    }

    /**
     * Handle unexpected profile loading errors
     */
    function handleProfileError(err) {
      currentUser = null;

      if (usernameInput) usernameInput.value = 'Unavailable';
      if (emailInput) emailInput.value = 'Unavailable';
      if (roleInput) roleInput.value = 'Unavailable';

      if (statusBadge) {
        statusBadge.className = 'badge badge-danger';
        statusBadge.textContent = 'Error Loading Profile';
      }

      if (statusBanner) {
        statusBanner.className = 'alert alert-danger';
        statusBanner.innerHTML = `
          <div class="alert-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
          <div class="alert-content">
            <div class="alert-title">Failed to Load Profile</div>
            <p style="margin: 0; font-size: 0.88rem;">${escapeHtml(err.message || 'Could not retrieve user profile.')}</p>
          </div>
        `;
      }

      if (btnExport) btnExport.disabled = true;
      if (btnDelete) btnDelete.disabled = true;
    }

    /**
     * Handle personal data export as downloadable JSON
     */
    async function handleDataExport() {
      if (!btnExport) return;
      if (!currentUser) {
        showToast('Please sign in to export your data.', 'warning');
        return;
      }

      const originalHtml = btnExport.innerHTML;
      btnExport.disabled = true;
      btnExport.innerHTML = `
        <svg class="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite;"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>
        Exporting...
      `;

      try {
        const response = await window.CyAwareAPI.exportUserData();

        if (response && response.success && response.data) {
          const jsonString = JSON.stringify(response.data, null, 2);
          const blob = new Blob([jsonString], { type: 'application/json' });
          const downloadUrl = URL.createObjectURL(blob);

          const usernameSlug = currentUser.username ? `${currentUser.username}-` : '';
          const filename = `cyaware-${usernameSlug}data-export.json`;

          const downloadLink = document.createElement('a');
          downloadLink.href = downloadUrl;
          downloadLink.download = filename;
          document.body.appendChild(downloadLink);
          downloadLink.click();
          document.body.removeChild(downloadLink);

          URL.revokeObjectURL(downloadUrl);
          showToast('Personal data archive downloaded successfully.', 'success');
        } else {
          throw new Error((response && response.message) || 'Failed to export data archive.');
        }
      } catch (err) {
        console.error('Data export failure:', err);
        showToast(err.message || 'Error occurred while exporting data archive.', 'danger');
      } finally {
        btnExport.disabled = false;
        btnExport.innerHTML = originalHtml;
      }
    }

    /**
     * Handle permanent account deletion
     */
    async function handleAccountDeletion() {
      if (!btnConfirmDelete) return;

      const originalHtml = btnConfirmDelete.innerHTML;
      btnConfirmDelete.disabled = true;
      btnConfirmDelete.innerHTML = `
        <svg class="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite;"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>
        Deleting...
      `;

      try {
        const response = await window.CyAwareAPI.deleteAccount();

        if (response && response.success) {
          closeModal('modal-delete-account-confirm');
          showToast(response.message || 'Account permanently deleted. Redirecting...', 'success', 3000);

          // Clear local UI state immediately
          currentUser = null;
          if (usernameInput) usernameInput.value = 'Account Deleted';
          if (emailInput) emailInput.value = 'Account Deleted';
          if (roleInput) roleInput.value = 'None';
          if (btnExport) btnExport.disabled = true;
          if (btnDelete) btnDelete.disabled = true;

          // Redirect to sign in / guest page after short delay
          setTimeout(function () {
            window.location.href = 'login.html';
          }, 1200);
        } else {
          throw new Error((response && response.message) || 'Account deletion failed.');
        }
      } catch (err) {
        console.error('Account deletion error:', err);
        btnConfirmDelete.disabled = false;
        btnConfirmDelete.innerHTML = originalHtml;
        closeModal('modal-delete-account-confirm');

        showToast(err.message || 'Failed to delete account.', 'danger', 5000);

        if (statusBanner) {
          statusBanner.className = 'alert alert-danger';
          statusBanner.innerHTML = `
            <div class="alert-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            </div>
            <div class="alert-content">
              <div class="alert-title">Account Deletion Failed</div>
              <p style="margin: 0; font-size: 0.88rem;">${escapeHtml(err.message || 'Failed to delete account.')}</p>
            </div>
          `;
        }
      }
    }
  }
})();

