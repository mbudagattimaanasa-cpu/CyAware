/**
 * CyAware — User Dashboard Controller
 * File: frontend/js/dashboard.js
 * 
 * Controls the User Dashboard workspace.
 * Queries window.CyAwareAPI.getDashboardData() for GET /api/dashboard.
 * Strictly adheres to project rules:
 * - Does not invent statistic field names or mock data.
 * - Displays honest pending-backend demonstration states.
 * - Keeps live integration dependent on backend schema confirmation.
 */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    initDashboard();
  });

  async function initDashboard() {
    const kpiTotal = document.getElementById('kpi-total-analyses');
    const kpiFlagged = document.getElementById('kpi-flagged-count');
    const kpiNormal = document.getElementById('kpi-normal-ratio');
    const recentContainer = document.getElementById('recent-activity-container');

    try {
      if (window.CyAwareAPI && window.CyAwareAPI.getDashboardData) {
        const response = await window.CyAwareAPI.getDashboardData();

        // If backend connection is pending, retain placeholder states honestly
        if (response.status === 'PENDING_BACKEND') {
          if (kpiTotal) kpiTotal.textContent = '--';
          if (kpiFlagged) kpiFlagged.textContent = '--';
          if (kpiNormal) kpiNormal.textContent = '--';
        }
      }
    } catch (err) {
      console.warn('Dashboard initialization notice:', err.message);
      if (window.CyAwareApp && window.CyAwareApp.showToast) {
        window.CyAwareApp.showToast('Dashboard awaiting backend connection: ' + err.message, 'info');
      }
    }
  }

})();

