/**
 * CyAware — User Dashboard Controller
 * File: frontend/js/dashboard.js
 * 
 * Connects the User Dashboard workspace to GET /api/dashboard via window.CyAwareAPI.
 * 
 * Strict Project Rules:
 * - Computes KPI metrics strictly from actual backend data.
 * - Handles division by zero and empty dataset states safely.
 * - Checks user authentication session via getMe() and handles session expiry gracefully.
 * - Never fabricates fake statistics or requests unsupported endpoints.
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
    initDashboard();
  });

  async function initDashboard() {
    const kpiTotal = document.getElementById('kpi-total-analyses');
    const kpiFlagged = document.getElementById('kpi-flagged-count');
    const kpiNormal = document.getElementById('kpi-normal-ratio');
    const statusBanner = document.getElementById('dashboard-status-banner');
    const recentContainer = document.getElementById('recent-activity-container');

    // 1. Verify API client availability
    if (!window.CyAwareAPI || typeof window.CyAwareAPI.getDashboardData !== 'function') {
      if (statusBanner) {
        statusBanner.className = 'alert alert-danger';
        statusBanner.innerHTML = `
          <div class="alert-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
          <div class="alert-content">
            <div class="alert-title">API Connection Unavailable</div>
            <p style="margin: 0; font-size: 0.88rem;">The CyAware API client is not loaded. Please verify application scripts.</p>
          </div>
        `;
      }
      return;
    }

    // 2. Safe authentication check via getMe() if available
    if (typeof window.CyAwareAPI.getMe === 'function') {
      try {
        const meRes = await window.CyAwareAPI.getMe();
        if (!meRes || !meRes.success || !meRes.data) {
          handleUnauthenticatedSession();
          return;
        }
      } catch (authErr) {
        if (authErr.status === 401 || authErr.code === 'UNAUTHENTICATED') {
          handleUnauthenticatedSession();
          return;
        }
      }
    }

    // 3. Fetch Dashboard Data
    try {
      const response = await window.CyAwareAPI.getDashboardData();

      if (response && response.success && response.data) {
        renderDashboardData(response.data);
      } else {
        throw new Error((response && response.message) || 'Failed to retrieve dashboard metrics.');
      }
    } catch (err) {
      console.warn('Dashboard fetch error:', err.code, err.message);

      if (err.status === 401 || err.code === 'UNAUTHENTICATED') {
        handleUnauthenticatedSession();
        return;
      }

      if (statusBanner) {
        statusBanner.className = 'alert alert-danger';
        statusBanner.innerHTML = `
          <div class="alert-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
          <div class="alert-content">
            <div class="alert-title">Failed to Load Dashboard</div>
            <p style="margin: 0; font-size: 0.88rem;">${escapeHtml(err.message || 'Error communicating with backend service.')}</p>
          </div>
        `;
      }
    }

    function handleUnauthenticatedSession() {
      if (kpiTotal) kpiTotal.textContent = '--';
      if (kpiFlagged) kpiFlagged.textContent = '--';
      if (kpiNormal) kpiNormal.textContent = '--';

      if (statusBanner) {
        statusBanner.className = 'alert alert-warning';
        statusBanner.innerHTML = `
          <div class="alert-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          </div>
          <div class="alert-content">
            <div class="alert-title">Authentication Required</div>
            <p style="margin: 0; font-size: 0.88rem;">
              Your session is expired or not authenticated. Please <a href="login.html" style="font-weight: 700; color: var(--color-primary); text-decoration: underline;">sign in</a> to access saved metrics and activity.
            </p>
          </div>
        `;
      }

      if (recentContainer) {
        recentContainer.innerHTML = `
          <div style="padding: 2rem; text-align: center; color: var(--color-text-dim);">
            <p style="margin-bottom: 1rem;">Please sign in to view your recent analysis history.</p>
            <a href="login.html" class="btn btn-primary btn-sm">Sign In to CyAware</a>
          </div>
        `;
      }
    }

    function renderDashboardData(data) {
      const totalSaved = Number(data.total_saved_count) || 0;
      const breakdown = data.category_breakdown || {};

      const normalCount = Number(breakdown['Normal']) || 0;
      const insultCount = Number(breakdown['Insult']) || 0;
      const threatCount = Number(breakdown['Threat']) || 0;
      const hateCount = Number(breakdown['Hate Speech']) || 0;
      const toxicCount = (Number(breakdown['Toxic/Abusive Language']) || 0) + (Number(breakdown['Toxic/Abusive']) || 0);

      const flaggedCount = insultCount + threatCount + hateCount + toxicCount;

      // 1. Render Total Saved KPI
      if (kpiTotal) {
        kpiTotal.textContent = totalSaved.toLocaleString();
        const subBadge = kpiTotal.parentElement ? kpiTotal.parentElement.querySelector('.stat-kpi-sub') : null;
        if (subBadge) {
          subBadge.innerHTML = `<span class="badge badge-normal" style="font-size: 0.72rem;">Saved Records</span>`;
        }
      }

      // 2. Render Flagged Detections KPI
      if (kpiFlagged) {
        kpiFlagged.textContent = flaggedCount.toLocaleString();
        const subBadge = kpiFlagged.parentElement ? kpiFlagged.parentElement.querySelector('.stat-kpi-sub') : null;
        if (subBadge) {
          subBadge.innerHTML = `<span class="badge" style="background: rgba(239, 68, 68, 0.15); color: #ef4444; font-size: 0.72rem;">Non-Normal Tone</span>`;
        }
      }

      // 3. Render Normal Ratio KPI (Safe division by zero handling)
      if (kpiNormal) {
        if (totalSaved > 0) {
          const ratioPct = ((normalCount / totalSaved) * 100).toFixed(1);
          kpiNormal.textContent = `${ratioPct}%`;
          const subBadge = kpiNormal.parentElement ? kpiNormal.parentElement.querySelector('.stat-kpi-sub') : null;
          if (subBadge) {
            subBadge.innerHTML = `<span class="badge badge-normal" style="font-size: 0.72rem;">${normalCount} of ${totalSaved} Normal</span>`;
          }
        } else {
          kpiNormal.textContent = '0%';
          const subBadge = kpiNormal.parentElement ? kpiNormal.parentElement.querySelector('.stat-kpi-sub') : null;
          if (subBadge) {
            subBadge.innerHTML = `<span class="badge" style="background: rgba(148, 163, 184, 0.1); color: var(--color-text-dim); font-size: 0.72rem;">0 Records</span>`;
          }
        }
      }

      // 4. Update Status Banner with Responsible AI Disclaimer
      if (statusBanner && data.confidence_disclaimer) {
        statusBanner.className = 'alert alert-responsible-ai';
        statusBanner.innerHTML = `
          <div class="alert-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          </div>
          <div class="alert-content">
            <div class="alert-title">Responsible AI Confidence Advisory</div>
            <p style="margin: 0; font-size: 0.88rem;">${escapeHtml(data.confidence_disclaimer)}</p>
          </div>
        `;
      }

      // 5. Render Recent Activity List
      if (recentContainer) {
        const recentList = Array.isArray(data.recent_activity) ? data.recent_activity : [];

        if (recentList.length === 0) {
          recentContainer.innerHTML = `
            <div style="width: 48px; height: 48px; border-radius: 50%; background: rgba(0, 210, 255, 0.1); color: var(--color-primary); display: flex; align-items: center; justify-content: center; margin: 0 auto 1rem auto;">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            </div>
            <div style="font-weight: 700; font-size: 1.1rem; margin-bottom: 0.35rem; color: var(--color-text-main);">
              No Historical Analyses Recorded Yet
            </div>
            <p style="font-size: 0.88rem; color: var(--color-text-dim); max-width: 480px; margin: 0 auto 1.25rem auto;">
              Perform a text analysis and opt in to save the record to start tracking your audit trail.
            </p>
            <a href="analyze-text.html" class="btn btn-primary btn-sm">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              Run First Analysis
            </a>
          `;
        } else {
          const itemsHtml = recentList.map(item => {
            const badgeCls = getCategoryBadgeClass(item.category);
            const dateStr = item.saved_at ? new Date(item.saved_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }) : '';
            const confStr = item.confidence != null ? (Number(item.confidence) * 100).toFixed(1) + '%' : 'N/A';
            const textPreview = item.text_content ? (item.text_content.length > 90 ? item.text_content.substring(0, 90) + '...' : item.text_content) : '—';

            return `
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.85rem 1rem; border-bottom: 1px solid var(--color-border-subtle); gap: 1rem;">
                <div style="text-align: left; flex: 1; min-width: 0;">
                  <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
                    <span class="badge ${badgeCls}" style="font-size: 0.75rem;">${escapeHtml(item.category)}</span>
                    <span style="font-size: 0.78rem; font-family: var(--font-family-mono); color: var(--color-text-dim);">${confStr}</span>
                    <span style="font-size: 0.75rem; color: var(--color-text-dim); margin-left: auto;">${escapeHtml(dateStr)}</span>
                  </div>
                  <div style="font-size: 0.88rem; color: var(--color-text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    "${escapeHtml(textPreview)}"
                  </div>
                </div>
              </div>
            `;
          }).join('');

          recentContainer.style.padding = '0';
          recentContainer.style.textAlign = 'left';
          recentContainer.innerHTML = `
            <div style="border-radius: var(--radius-md); overflow: hidden;">
              ${itemsHtml}
            </div>
            <div style="padding: 0.75rem 1rem; text-align: right; background: rgba(0, 0, 0, 0.1);">
              <a href="history.html" style="font-size: 0.82rem; color: var(--color-primary); font-weight: 600;">View all records in Audit History &rarr;</a>
            </div>
          `;
        }
      }
    }
  }
})();
