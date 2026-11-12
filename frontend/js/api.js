/**
 * CyAware — API Client Layer
 * File: frontend/js/api.js
 * 
 * Centralized API client module connecting the frontend to the CyAware Flask backend.
 * Strictly adheres to the Shared API Contract (docs/api_contract.md).
 * 
 * Implemented Endpoints:
 * - GET  /api/health
 * - POST /api/auth/register
 * - POST /api/auth/login
 * - POST /api/auth/logout
 * - GET  /api/auth/me
 * - GET  /api/auth/csrf-token
 * - POST /api/analyze/text
 * - POST /api/analyze/file
 * - POST /api/analyze/image
 * - POST /api/analyze/conversation
 * - GET  /api/dashboard
 * - GET  /api/analyses
 * - DELETE /api/analyses/{id}
 * - GET  /api/user/export
 * - DELETE /api/user/account
 * 
 * Placeholders (unimplemented in backend):
 * - GET  /api/admin/dashboard (returns status: PENDING_BACKEND)
 * - GET  /api/reports/{id}     (returns status: PENDING_BACKEND)
 * - POST /api/feedback         (returns status: PENDING_BACKEND)
 */

(function () {
  'use strict';

  const config = window.CyAwareConfig || {
    API_BASE_URL: '/api'
  };

  const API_BASE = config.API_BASE_URL || '/api';

  // In-memory CSRF token cache
  let cachedCsrfToken = null;

  /**
   * Retrieve or establish CSRF token for the active session.
   * Target: GET /api/auth/csrf-token
   */
  async function getCsrfToken(forceRefresh = false) {
    if (cachedCsrfToken && !forceRefresh) {
      return cachedCsrfToken;
    }
    try {
      const response = await fetch(`${API_BASE}/auth/csrf-token`, {
        method: 'GET',
        credentials: 'same-origin',
        headers: { 'Accept': 'application/json' }
      });
      if (response.ok) {
        const json = await response.json();
        if (json && json.data && json.data.csrf_token) {
          cachedCsrfToken = json.data.csrf_token;
          return cachedCsrfToken;
        }
      }
    } catch (e) {
      console.warn('Failed to retrieve CSRF token:', e.message);
    }
    return cachedCsrfToken;
  }

  /**
   * Internal HTTP request helper enforcing same-origin credentials,
   * CSRF protection, and error propagation.
   */
  async function request(endpoint, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${cleanEndpoint}`;

    const headers = options.headers ? { ...options.headers } : {};

    // For non-GET requests without FormData, default to application/json
    if (!options.isFormData && !headers['Content-Type'] && method !== 'GET') {
      headers['Content-Type'] = 'application/json';
    }
    if (!headers['Accept']) {
      headers['Accept'] = 'application/json';
    }

    // Attach CSRF token on state-changing requests if available
    const isStateChanging = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method);
    if (isStateChanging) {
      const token = await getCsrfToken();
      if (token) {
        headers['X-CSRF-Token'] = token;
      }
    }

    const fetchOptions = {
      method,
      headers,
      credentials: 'same-origin'
    };

    if (options.body) {
      fetchOptions.body = options.body;
    }

    const response = await fetch(url, fetchOptions);

    // If 403 CSRF_ERROR occurs on a state-changing request, refresh token and retry once
    if (response.status === 403 && isStateChanging && !options._retried) {
      const errorData = await response.clone().json().catch(() => null);
      if (errorData && errorData.error && errorData.error.code === 'CSRF_ERROR') {
        const refreshedToken = await getCsrfToken(true);
        if (refreshedToken) {
          headers['X-CSRF-Token'] = refreshedToken;
          return request(endpoint, { ...options, headers, _retried: true });
        }
      }
    }

    let resultJson = null;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      resultJson = await response.json().catch(() => null);
    }

    if (!response.ok) {
      const message = (resultJson && resultJson.error && resultJson.error.message) ||
                      (resultJson && resultJson.message) ||
                      `HTTP error ${response.status}: ${response.statusText}`;
      const code = (resultJson && resultJson.error && resultJson.error.code) || 'HTTP_ERROR';
      const error = new Error(message);
      error.status = response.status;
      error.code = code;
      error.response = resultJson;
      throw error;
    }

    return resultJson;
  }

  /**
   * Health Check
   * Target: GET /api/health
   */
  async function checkBackendConnection() {
    try {
      const res = await request('/health', { method: 'GET' });
      return {
        connected: res && res.success === true,
        data: res ? res.data : null,
        message: res ? res.message : 'API is operational.'
      };
    } catch (e) {
      return {
        connected: false,
        error: e.message,
        message: 'Could not connect to backend API.'
      };
    }
  }

  /**
   * User Registration
   * Target: POST /api/auth/register
   * Payload: { username, email, password }
   */
  async function register(userData) {
    if (!userData || !userData.username || !userData.email || !userData.password) {
      throw new Error('Registration error: username, email, and password are required.');
    }
    return request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        username: String(userData.username).trim(),
        email: String(userData.email).trim().toLowerCase(),
        password: String(userData.password)
      })
    });
  }

  /**
   * User Login
   * Target: POST /api/auth/login
   * Payload: { username_or_email, password }
   */
  async function login(credentials) {
    if (!credentials || (!credentials.username_or_email && !credentials.email && !credentials.username) || !credentials.password) {
      throw new Error('Login error: username/email and password are required.');
    }
    const identifier = String(credentials.username_or_email || credentials.email || credentials.username).trim();
    const res = await request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        username_or_email: identifier,
        password: String(credentials.password)
      })
    });
    if (res && res.data && res.data.csrf_token) {
      cachedCsrfToken = res.data.csrf_token;
    }
    return res;
  }

  /**
   * User Logout
   * Target: POST /api/auth/logout
   */
  async function logout() {
    const res = await request('/auth/logout', {
      method: 'POST'
    });
    cachedCsrfToken = null;
    return res;
  }

  /**
   * Authenticated User Profile
   * Target: GET /api/auth/me
   */
  async function getMe() {
    return request('/auth/me', { method: 'GET' });
  }

  /**
   * Text Analysis (Single Message)
   * Target: POST /api/analyze/text
   * Payload: { text, save: boolean }
   */
  async function submitTextAnalysis(text, saveOptIn = false) {
    if (!text || typeof text !== 'string' || !text.trim()) {
      throw new Error('Analysis payload error: text content cannot be empty.');
    }
    return request('/analyze/text', {
      method: 'POST',
      body: JSON.stringify({
        text: text.trim(),
        save: Boolean(saveOptIn)
      })
    });
  }

  /**
   * Document File Batch Analysis (.csv, .txt)
   * Target: POST /api/analyze/file
   * Payload: FormData with form field 'file'
   */
  async function submitFileAnalysis(file) {
    if (!file) {
      throw new Error('Analysis payload error: no document file selected.');
    }
    const formData = new FormData();
    formData.append('file', file);

    return request('/analyze/file', {
      method: 'POST',
      body: formData,
      isFormData: true
    });
  }

  /**
   * Chat Screenshot OCR Analysis (.png, .jpg, .jpeg)
   * Target: POST /api/analyze/image
   * Payload: FormData with form field 'image'
   */
  async function submitImageAnalysis(imageFile) {
    if (!imageFile) {
      throw new Error('Analysis payload error: no image file selected.');
    }
    const formData = new FormData();
    formData.append('image', imageFile);

    return request('/analyze/image', {
      method: 'POST',
      body: formData,
      isFormData: true
    });
  }

  /**
   * Multi-Turn Sequential Conversation Analysis
   * Target: POST /api/analyze/conversation
   * Payload: { messages: [ { text, speaker, timestamp } ] }
   */
  async function submitConversationAnalysis(messages) {
    if (!messages || !Array.isArray(messages) || messages.length < 2 || messages.length > 50) {
      throw new Error('Analysis payload error: conversation must contain between 2 and 50 messages.');
    }
    return request('/analyze/conversation', {
      method: 'POST',
      body: JSON.stringify({ messages })
    });
  }

  /**
   * User Dashboard Statistics
   * Target: GET /api/dashboard
   */
  async function getDashboardData() {
    return request('/dashboard', { method: 'GET' });
  }

  /**
   * User Analysis History
   * Target: GET /api/analyses
   * Query params: page, limit, category
   */
  async function getAnalysesHistory(params = {}) {
    const query = new URLSearchParams();
    if (params.page) query.append('page', params.page);
    if (params.limit) query.append('limit', params.limit);
    if (params.category) query.append('category', params.category);

    const queryString = query.toString();
    const endpoint = queryString ? `/analyses?${queryString}` : '/analyses';
    return request(endpoint, { method: 'GET' });
  }

  /**
   * Delete Saved Analysis Record
   * Target: DELETE /api/analyses/{id}
   */
  async function deleteAnalysis(id) {
    if (!id) {
      throw new Error('Analysis ID is required for deletion.');
    }
    return request(`/analyses/${encodeURIComponent(id)}`, {
      method: 'DELETE'
    });
  }

  /**
   * Export User Data
   * Target: GET /api/user/export
   * Returns: { success: true, data: { profile, saved_analyses, feedback } }
   * Enforces authenticated session.
   */
  async function exportUserData() {
    return request('/user/export', { method: 'GET' });
  }

  /**
   * Delete User Account & Associated Data
   * Target: DELETE /api/user/account
   * Enforces CSRF token and authenticated session.
   * Clears cached CSRF token upon successful deletion.
   */
  async function deleteAccount() {
    const res = await request('/user/account', {
      method: 'DELETE'
    });
    cachedCsrfToken = null;
    return res;
  }

  /**
   * Report Download Placeholder
   * Notice: Unimplemented in backend; kept as honest placeholder.
   */
  async function getReport(id) {
    return {
      status: 'PENDING_BACKEND',
      message: 'Report download endpoint is not implemented on the backend.'
    };
  }

  /**
   * Feedback Submission Placeholder
   * Notice: Unimplemented in backend; kept as honest placeholder.
   */
  async function submitFeedback(payload) {
    return {
      status: 'PENDING_BACKEND',
      message: 'Feedback submission endpoint is not implemented on the backend.'
    };
  }

  /**
   * Admin Dashboard Placeholder
   * Notice: Unimplemented in backend; kept as harmless placeholder for admin.js.
   */
  async function getAdminDashboard() {
    return {
      status: 'PENDING_BACKEND',
      message: 'Admin dashboard endpoint is not implemented on the backend.'
    };
  }

  // Export to global window scope
  window.CyAwareAPI = Object.freeze({
    checkBackendConnection,
    getCsrfToken,
    register,
    login,
    logout,
    getMe,
    submitTextAnalysis,
    submitFileAnalysis,
    submitImageAnalysis,
    submitConversationAnalysis,
    getDashboardData,
    getAnalysesHistory,
    deleteAnalysis,
    exportUserData,
    deleteAccount,
    getReport,
    submitFeedback,
    getAdminDashboard
  });
})();
