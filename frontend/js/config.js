/**
 * CyAware — Frontend Configuration & Contract Endpoints
 * File: frontend/js/config.js
 * 
 * NOTE: Strictly follows the Shared API Contract Prompt and Backend Implementation.
 * Includes user privacy & account management endpoints implemented in backend Stage 5.
 */

const CyAwareConfig = Object.freeze({
  // Base URL for backend API (can be overridden via environment/proxy)
  API_BASE_URL: window.CYAWARE_API_BASE || '/api',

  // Contract & Backend Endpoints
  ENDPOINTS: Object.freeze({
    // Authentication
    AUTH_REGISTER: '/api/auth/register',
    AUTH_LOGIN: '/api/auth/login',
    AUTH_LOGOUT: '/api/auth/logout',
    AUTH_ME: '/api/auth/me',
    AUTH_CSRF_TOKEN: '/api/auth/csrf-token',

    // Analysis Engines
    ANALYZE_TEXT: '/api/analyze/text',
    ANALYZE_FILE: '/api/analyze/file',
    ANALYZE_IMAGE: '/api/analyze/image',
    ANALYZE_CONVERSATION: '/api/analyze/conversation',

    // History & Reports
    ANALYSES: '/api/analyses',
    ANALYSIS_BY_ID: (id) => `/api/analyses/${encodeURIComponent(id)}`,
    REPORT_BY_ID: (id) => `/api/reports/${encodeURIComponent(id)}`, // Unimplemented in backend; placeholder

    // Dashboards & Feedback
    DASHBOARD: '/api/dashboard',
    ADMIN_DASHBOARD: '/api/admin/dashboard', // Unimplemented in backend; placeholder
    FEEDBACK: '/api/feedback', // Unimplemented in backend; placeholder

    // User Privacy & Account Management
    USER_EXPORT: '/api/user/export',
    USER_ACCOUNT_DELETE: '/api/user/account'
  }),

  // Agreed 5 Classification Categories
  CATEGORIES: Object.freeze([
    'Normal',
    'Insult',
    'Threat',
    'Hate Speech',
    'Toxic/Abusive Language'
  ]),

  // Responsible AI Advisory Notice
  RESPONSIBLE_AI_NOTICE: "Responsible AI Advisory: Language requires context. A single detected statement does not constitute definitive proof of cyberbullying without comprehensive situational analysis. CyAware operates as an assistive intelligence layer, strictly avoiding automated punitive or blocking actions.",

  // Mock Mode: Disabled by default. Only used when explicitly enabled for UI layout testing.
  MOCK_MODE: false
});

// Export to global window scope for vanilla JS usage
window.CyAwareConfig = CyAwareConfig;

