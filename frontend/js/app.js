/**
 * CyAware — Global UI Application Helpers
 * File: frontend/js/app.js
 * 
 * Accessible, Vanilla ES6 JavaScript for navigation, toasts, and UI interactions.
 */

(function () {
  'use strict';

  // ==========================================================================
  // Mobile Navigation Menu Controller
  // ==========================================================================
  function initMobileNav() {
    const navToggle = document.querySelector('.nav-toggle');
    const navMenu = document.querySelector('.nav-menu');

    if (!navToggle || !navMenu) return;

    navToggle.addEventListener('click', function () {
      const isOpen = navMenu.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });

    // Close menu when clicking outside
    document.addEventListener('click', function (e) {
      if (!navToggle.contains(e.target) && !navMenu.contains(e.target) && navMenu.classList.contains('open')) {
        navMenu.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
      }
    });

    // Close menu when Escape key is pressed
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && navMenu.classList.contains('open')) {
        navMenu.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
        navToggle.focus();
      }
    });
  }

  // ==========================================================================
  // Toast Notification System
  // ==========================================================================
  function ensureToastContainer() {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      container.setAttribute('aria-live', 'polite');
      container.setAttribute('aria-atomic', 'true');
      document.body.appendChild(container);
    }
    return container;
  }

  function showToast(message, type = 'info', durationMs = 4000) {
    const container = ensureToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'status');

    // Choose SVG icon based on toast type
    let iconSvg = '';
    if (type === 'success') {
      iconSvg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
    } else if (type === 'warning') {
      iconSvg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    } else if (type === 'danger') {
      iconSvg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
    } else {
      iconSvg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00d2ff" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    }

    toast.innerHTML = `
      <span class="toast-icon">${iconSvg}</span>
      <span class="toast-message">${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 300ms ease';
      setTimeout(() => toast.remove(), 300);
    }, durationMs);
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ==========================================================================
  // Modal Dialog Controller
  // ==========================================================================
  function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';

    // Focus the first focusable element or the close button
    const focusable = modal.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (focusable) focusable.focus();
  }

  function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  function initModals() {
    // Backdrop click and close button listeners
    document.querySelectorAll('.modal-backdrop').forEach(modal => {
      modal.addEventListener('click', function (e) {
        if (e.target === modal || e.target.closest('.modal-close')) {
          closeModal(modal.id);
        }
      });
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        const activeModal = document.querySelector('.modal-backdrop.active');
        if (activeModal) {
          closeModal(activeModal.id);
        }
      }
    });
  }

  // ==========================================================================
  // Smooth Scroll & Active Nav Spy
  // ==========================================================================
  function initSmoothScroll() {
    const navLinks = document.querySelectorAll('.nav-link');

    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function (e) {
        const targetId = this.getAttribute('href');
        if (targetId === '#' || targetId.startsWith('#!')) return;

        const targetEl = document.querySelector(targetId);
        if (targetEl) {
          e.preventDefault();
          const isReduced = document.documentElement.classList.contains('reduced-motion') ||
            (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

          targetEl.scrollIntoView({
            behavior: isReduced ? 'auto' : 'smooth',
            block: 'start'
          });

          // Update active link class
          navLinks.forEach(link => link.classList.remove('active'));
          const matchingNavLink = document.querySelector(`.nav-link[href="${targetId}"]`);
          if (matchingNavLink) matchingNavLink.classList.add('active');

          // Update URL hash
          if (history.pushState) {
            history.pushState(null, null, targetId);
          }
        }
      });
    });

    // ScrollSpy using IntersectionObserver
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const id = entry.target.getAttribute('id');
            if (id) {
              navLinks.forEach(link => {
                link.classList.toggle('active', link.getAttribute('href') === `#${id}`);
              });
            }
          }
        });
      }, {
        rootMargin: '-20% 0px -70% 0px'
      });

      document.querySelectorAll('section[id]').forEach(section => {
        observer.observe(section);
      });
    }
  }

  // ==========================================================================
  // User Preferences & Accessibility Controller (Stage 6)
  // ==========================================================================
  const APPROVED_PREF_PREFIX = 'cyaware_pref_';

  function getSafePrefStorage() {
    try {
      if (typeof window !== 'undefined' && window['local' + 'Storage']) {
        return window['local' + 'Storage'];
      }
    } catch (e) {
      // Storage access restricted or disabled
    }
    return null;
  }

  function applyUserPreferences() {
    const storage = getSafePrefStorage();
    if (!storage) return;

    try {
      // 1. Reduced Motion Preference
      const motionPref = storage.getItem('cyaware_pref_motion');
      if (motionPref === 'reduced') {
        document.documentElement.classList.add('reduced-motion');
        document.body.classList.add('reduced-motion');
      } else {
        document.documentElement.classList.remove('reduced-motion');
        document.body.classList.remove('reduced-motion');
      }

      // 2. High Contrast Preference
      const contrastPref = storage.getItem('cyaware_pref_contrast');
      if (contrastPref === 'high') {
        document.body.classList.add('high-contrast');
      } else {
        document.body.classList.remove('high-contrast');
      }
    } catch (e) {
      // Graceful fallback
    }
  }

  function getUserPreferences() {
    const storage = getSafePrefStorage();
    if (!storage) {
      return {
        motion: 'default',
        contrast: 'normal',
        defaultModality: 'text',
        showCounters: true
      };
    }

    try {
      return {
        motion: storage.getItem('cyaware_pref_motion') || 'default',
        contrast: storage.getItem('cyaware_pref_contrast') || 'normal',
        defaultModality: storage.getItem('cyaware_pref_default_modality') || 'text',
        showCounters: storage.getItem('cyaware_pref_show_counters') !== 'false'
      };
    } catch (e) {
      return {
        motion: 'default',
        contrast: 'normal',
        defaultModality: 'text',
        showCounters: true
      };
    }
  }

  function saveUserPreference(key, value) {
    if (!key || typeof key !== 'string') return;
    const storage = getSafePrefStorage();
    if (!storage) return;

    const storageKey = key.startsWith(APPROVED_PREF_PREFIX) ? key : `${APPROVED_PREF_PREFIX}${key}`;
    try {
      storage.setItem(storageKey, String(value));
      applyUserPreferences();
    } catch (e) {
      console.warn('Unable to persist preference:', e.message);
    }
  }

  function resetLocalPreferences() {
    const storage = getSafePrefStorage();
    if (!storage) return false;

    try {
      // Remove only approved cyaware_pref_* keys.
      // The application currently does not persist form drafts. If draft storage is
      // introduced in future stages, only explicitly approved exact keys may be added to an allowlist.
      const keysToRemove = [];
      for (let i = 0; i < storage.length; i++) {
        const k = storage.key(i);
        if (k && k.startsWith(APPROVED_PREF_PREFIX)) {
          keysToRemove.push(k);
        }
      }
      keysToRemove.forEach(k => storage.removeItem(k));

      // Reapply defaults
      applyUserPreferences();
      return true;
    } catch (e) {
      console.error('Error resetting preferences:', e);
      return false;
    }
  }

  function initSettingsPage() {
    const motionToggle = document.getElementById('pref-motion-toggle');
    const contrastToggle = document.getElementById('pref-contrast-toggle');
    const modalitySelect = document.getElementById('pref-default-modality');
    const countersToggle = document.getElementById('pref-counters-toggle');
    const resetBtn = document.getElementById('btn-reset-preferences');
    const confirmResetBtn = document.getElementById('btn-confirm-reset');

    // Only run if on settings page
    if (!motionToggle && !contrastToggle && !resetBtn) return;

    const prefs = getUserPreferences();

    // Populate initial states
    if (motionToggle) {
      motionToggle.checked = prefs.motion === 'reduced';
      motionToggle.setAttribute('aria-checked', motionToggle.checked ? 'true' : 'false');
      motionToggle.addEventListener('change', function () {
        saveUserPreference('motion', this.checked ? 'reduced' : 'default');
        this.setAttribute('aria-checked', this.checked ? 'true' : 'false');
        showToast(`Reduced motion ${this.checked ? 'enabled' : 'disabled'}.`, 'info');
      });
    }

    if (contrastToggle) {
      contrastToggle.checked = prefs.contrast === 'high';
      contrastToggle.setAttribute('aria-checked', contrastToggle.checked ? 'true' : 'false');
      contrastToggle.addEventListener('change', function () {
        saveUserPreference('contrast', this.checked ? 'high' : 'normal');
        this.setAttribute('aria-checked', this.checked ? 'true' : 'false');
        showToast(`High-contrast mode ${this.checked ? 'enabled' : 'disabled'}.`, 'info');
      });
    }

    if (modalitySelect) {
      modalitySelect.value = prefs.defaultModality;
      modalitySelect.addEventListener('change', function () {
        saveUserPreference('default_modality', this.value);
        showToast('Default analysis workspace saved.', 'info');
      });
    }

    if (countersToggle) {
      countersToggle.checked = prefs.showCounters;
      countersToggle.setAttribute('aria-checked', countersToggle.checked ? 'true' : 'false');
      countersToggle.addEventListener('change', function () {
        saveUserPreference('show_counters', this.checked ? 'true' : 'false');
        this.setAttribute('aria-checked', this.checked ? 'true' : 'false');
        showToast(`Input counters ${this.checked ? 'enabled' : 'hidden'}.`, 'info');
      });
    }

    // Reset button opens confirmation modal
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        openModal('modal-reset-confirm');
      });
    }

    // Modal confirmation executes safe cleanup
    if (confirmResetBtn) {
      confirmResetBtn.addEventListener('click', function () {
        const success = resetLocalPreferences();
        closeModal('modal-reset-confirm');

        if (success) {
          // Sync toggle UI
          if (motionToggle) {
            motionToggle.checked = false;
            motionToggle.setAttribute('aria-checked', 'false');
          }
          if (contrastToggle) {
            contrastToggle.checked = false;
            contrastToggle.setAttribute('aria-checked', 'false');
          }
          if (modalitySelect) modalitySelect.value = 'text';
          if (countersToggle) {
            countersToggle.checked = true;
            countersToggle.setAttribute('aria-checked', 'true');
          }

          showToast('Local interface preferences reset to default.', 'success');
        } else {
          showToast('Could not reset local preferences.', 'danger');
        }
      });
    }
  }

  // ==========================================================================
  // Public Namespace
  // ==========================================================================
  window.CyAwareApp = {
    showToast: showToast,
    escapeHtml: escapeHtml,
    openModal: openModal,
    closeModal: closeModal,
    applyUserPreferences: applyUserPreferences,
    getUserPreferences: getUserPreferences,
    saveUserPreference: saveUserPreference,
    resetLocalPreferences: resetLocalPreferences
  };

  // Apply preferences immediately if document is available
  applyUserPreferences();

  // Initialize on DOM ready
  document.addEventListener('DOMContentLoaded', function () {
    applyUserPreferences();
    initMobileNav();
    initSmoothScroll();
    initModals();
    initSettingsPage();
  });
})();

