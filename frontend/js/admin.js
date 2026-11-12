/**
 * CyAware — Administrative Console Controller
 * File: frontend/js/admin.js
 *
 * Controls the Administrative Console interface.
 * Targets confirmed endpoint GET /api/admin/dashboard via CyAwareAPI.getAdminDashboard().
 *
 * Strict Project Rules:
 * - Does not invent user lists, feedback items, or platform KPI statistics.
 * - Displays honest pending-backend demonstration states.
 * - Supports accessible tab navigation with ARIA attributes and keyboard controls.
 * - Does not make speculative API requests.
 */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    verifyAndInitAdminConsole();
  });

  /**
   * Verify administrative role before revealing console
   * Enforces client-side defense-in-depth:
   * - Guests are redirected to login.html
   * - Ordinary users ('user') are redirected to dashboard.html
   * - Only 'admin' role unhides #main-content and initializes tabs
   */
  async function verifyAndInitAdminConsole() {
    const mainContent = document.getElementById('main-content');

    let user = null;
    try {
      if (window.CyAwareApp && typeof window.CyAwareApp.getSessionUser === 'function') {
        user = await window.CyAwareApp.getSessionUser();
      } else if (window.CyAwareAPI && typeof window.CyAwareAPI.getMe === 'function') {
        const res = await window.CyAwareAPI.getMe();
        if (res && res.success && res.data && res.data.user) {
          user = res.data.user;
        }
      }
    } catch (err) {
      user = null;
    }

    // 1. Guest Handling
    if (!user) {
      window.location.replace('login.html');
      return;
    }

    // 2. Ordinary Authenticated User Handling
    if (user.role !== 'admin') {
      if (window.CyAwareApp && typeof window.CyAwareApp.showToast === 'function') {
        window.CyAwareApp.showToast('Access denied: Administrator privileges required.', 'danger');
      }
      window.location.replace('dashboard.html');
      return;
    }

    // 3. Administrator Handling: Reveal existing admin interface
    if (mainContent) {
      mainContent.style.display = '';
    }

    initAdminConsole();
  }

  async function initAdminConsole() {
    initAccessibleTabs();
    await loadAdminDashboardData();
  }

  /**
   * Accessible Tab Navigation Controller
   * Supports click and keyboard navigation (ArrowLeft, ArrowRight, Home, End)
   */
  function initAccessibleTabs() {
    const tabs = Array.from(document.querySelectorAll('.admin-tab'));
    const panels = Array.from(document.querySelectorAll('.admin-tabpanel'));

    if (tabs.length === 0 || panels.length === 0) return;

    tabs.forEach((tab, index) => {
      // Click handler
      tab.addEventListener('click', function () {
        activateTab(tab, tabs, panels);
      });

      // Keyboard handler (WAI-ARIA Tab Pattern)
      tab.addEventListener('keydown', function (e) {
        let targetIndex = null;

        if (e.key === 'ArrowRight') {
          targetIndex = (index + 1) % tabs.length;
        } else if (e.key === 'ArrowLeft') {
          targetIndex = (index - 1 + tabs.length) % tabs.length;
        } else if (e.key === 'Home') {
          targetIndex = 0;
        } else if (e.key === 'End') {
          targetIndex = tabs.length - 1;
        }

        if (targetIndex !== null) {
          e.preventDefault();
          tabs[targetIndex].focus();
          activateTab(tabs[targetIndex], tabs, panels);
        }
      });
    });
  }

  function activateTab(selectedTab, allTabs, allPanels) {
    const targetPanelId = selectedTab.getAttribute('aria-controls');

    allTabs.forEach(tab => {
      const isSelected = tab === selectedTab;
      tab.classList.toggle('active', isSelected);
      tab.setAttribute('aria-selected', isSelected ? 'true' : 'false');
      tab.setAttribute('tabindex', isSelected ? '0' : '-1');
    });

    allPanels.forEach(panel => {
      const isTarget = panel.id === targetPanelId;
      panel.classList.toggle('active', isTarget);
      if (isTarget) {
        panel.setAttribute('tabindex', '0');
      } else {
        panel.removeAttribute('tabindex');
      }
    });
  }

  /**
   * Data Loader for GET /api/admin/dashboard
   */
  async function loadAdminDashboardData() {
    const kpiUsers = document.getElementById('admin-kpi-users');
    const kpiAnalyses = document.getElementById('admin-kpi-analyses');
    const kpiFlagged = document.getElementById('admin-kpi-flagged');
    const kpiFeedback = document.getElementById('admin-kpi-feedback');

    try {
      if (window.CyAwareAPI && window.CyAwareAPI.getAdminDashboard) {
        const response = await window.CyAwareAPI.getAdminDashboard();

        // Pending backend status: retain neutral placeholder states honestly
        if (response.status === 'PENDING_BACKEND') {
          if (kpiUsers) kpiUsers.textContent = '--';
          if (kpiAnalyses) kpiAnalyses.textContent = '--';
          if (kpiFlagged) kpiFlagged.textContent = '--';
          if (kpiFeedback) kpiFeedback.textContent = '--';
        }
      }
    } catch (err) {
      console.warn('Admin console data notice:', err.message);
      if (window.CyAwareApp && window.CyAwareApp.showToast) {
        window.CyAwareApp.showToast('Admin data awaiting backend connection: ' + err.message, 'info');
      }
    }
  }

})();
