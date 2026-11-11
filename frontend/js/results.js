/**
 * CyAware — Analysis Results Controller
 * File: frontend/js/results.js
 * 
 * Controls the Analysis Results & Assessment page.
 * Targets POST /api/feedback and GET /api/reports/{id}.
 * 
 * Strict Project Rules:
 * - Does not generate fake predictions, confidence scores, or mock tokens.
 * - Displays honest pending-backend demonstration states.
 * - Keeps feedback submission disabled until request schema is confirmed.
 * - Does not simulate successful report downloads; supports clean print stylesheet.
 */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    initResultsPage();
  });

  function initResultsPage() {
    const printBtn = document.getElementById('btn-print-report');
    const downloadBtn = document.getElementById('btn-download-report');
    const contextBox = document.getElementById('result-context-container');

    // Check URL parameters for any demonstration context passed from workspace
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const textParam = urlParams.get('text');
      if (textParam && contextBox) {
        contextBox.textContent = textParam;
      }
    } catch (e) {
      // Graceful fallback to default demonstration context
    }

    // Print action triggers browser print dialog styled via @media print
    if (printBtn) {
      printBtn.addEventListener('click', function () {
        window.print();
      });
    }

    // Download button kept disabled with honest notice
    if (downloadBtn) {
      downloadBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast('Report download is disabled pending backend format confirmation (JSON vs PDF).', 'warning');
        }
      });
    }
  }

})();

