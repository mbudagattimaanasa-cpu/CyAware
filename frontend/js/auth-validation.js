/**
 * CyAware — Client-Side Authentication Controller & Form Validation
 * File: frontend/js/auth-validation.js
 * 
 * Connects frontend authentication forms directly to the CyAware backend API:
 * - Registration: POST /api/auth/register (username, email, password)
 * - Login: POST /api/auth/login (username_or_email, password)
 * - Session Management: Server-managed HttpOnly session cookies (SameSite=Lax)
 * - CSRF Protection: Managed transparently via window.CyAwareAPI
 * 
 * Strict Project Rules:
 * - Passwords, session IDs, and authentication tokens are NEVER stored in localStorage/sessionStorage.
 * - Real backend responses dictate authentication and error states.
 */

(function () {
  'use strict';

  // Backend validation constraints
  const USERNAME_REGEX = /^[a-zA-Z0-9_]{3,30}$/;
  const EMAIL_REGEX = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

  // ==========================================================================
  // Validation Utilities
  // ==========================================================================
  function isValidUsername(username) {
    return USERNAME_REGEX.test(String(username).trim());
  }

  function isValidEmail(email) {
    const trimmed = String(email).trim();
    return trimmed.length <= 120 && EMAIL_REGEX.test(trimmed);
  }

  function setFieldError(field, errorMessage) {
    if (!field) return;
    field.classList.add('is-invalid');
    field.classList.remove('is-valid');
    field.setAttribute('aria-invalid', 'true');

    const errorContainer = document.getElementById(`${field.id}-error`);
    if (errorContainer) {
      errorContainer.textContent = errorMessage;
      errorContainer.style.display = 'flex';
    }
  }

  function clearFieldError(field) {
    if (!field) return;
    field.classList.remove('is-invalid');
    field.removeAttribute('aria-invalid');

    const errorContainer = document.getElementById(`${field.id}-error`);
    if (errorContainer) {
      errorContainer.textContent = '';
      errorContainer.style.display = 'none';
    }
  }

  function setFieldValid(field) {
    if (!field) return;
    clearFieldError(field);
    field.classList.add('is-valid');
  }

  function showStatusBanner(banner, message, type = 'danger') {
    if (!banner) return;
    banner.className = `alert alert-${type}`;
    banner.style.display = 'flex';

    let iconSvg = '';
    if (type === 'success') {
      iconSvg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
    } else if (type === 'warning') {
      iconSvg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    } else {
      iconSvg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
    }

    banner.innerHTML = `
      <div class="alert-icon">${iconSvg}</div>
      <div class="alert-content">
        <p style="margin: 0; font-size: 0.9rem;">${escapeHtml(message)}</p>
      </div>
    `;
  }

  function hideStatusBanner(banner) {
    if (!banner) return;
    banner.style.display = 'none';
    banner.innerHTML = '';
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ==========================================================================
  // Password Visibility Toggle
  // ==========================================================================
  function initPasswordToggles() {
    const toggleButtons = document.querySelectorAll('.password-toggle-btn');

    toggleButtons.forEach(btn => {
      btn.addEventListener('click', function () {
        const targetId = this.getAttribute('data-target');
        const input = document.getElementById(targetId);
        if (!input) return;

        const isPassword = input.getAttribute('type') === 'password';
        input.setAttribute('type', isPassword ? 'text' : 'password');
        this.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');

        if (isPassword) {
          this.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
              <line x1="1" y1="1" x2="23" y2="23"></line>
            </svg>
          `;
        } else {
          this.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
          `;
        }
      });
    });
  }

  // ==========================================================================
  // Password Strength Evaluation (for Registration)
  // ==========================================================================
  function evaluatePasswordStrength(password) {
    if (!password || password.length === 0) return { score: 0, text: '' };

    let score = 0;
    if (password.length >= 8) score++;
    if (/[a-zA-Z]/.test(password) && /[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;

    if (score === 0) score = 1;

    let label = 'Weak';
    if (score === 2) label = 'Medium';
    if (score === 3) label = 'Strong';

    return { score, text: label };
  }

  function updateStrengthMeter(password) {
    const meter = document.getElementById('password-strength-meter');
    const label = document.getElementById('password-strength-label');
    if (!meter || !label) return;

    const { score, text } = evaluatePasswordStrength(password);
    const steps = meter.querySelectorAll('.strength-step');

    steps.forEach((step, index) => {
      step.className = 'strength-step';
      if (index < score) {
        if (score === 1) step.classList.add('weak');
        if (score === 2) step.classList.add('medium');
        if (score === 3) step.classList.add('strong');
      }
    });

    label.textContent = text ? `Strength: ${text}` : 'Minimum 8 characters with letters and numbers';
  }

  // ==========================================================================
  // Login Form Controller
  // ==========================================================================
  function initLoginForm() {
    const form = document.getElementById('login-form');
    if (!form) return;

    const identifierInput = document.getElementById('login-email');
    const passwordInput = document.getElementById('login-password');
    const statusBanner = document.getElementById('login-status-banner');
    const submitBtn = form.querySelector('button[type="submit"]');

    if (identifierInput) {
      identifierInput.addEventListener('input', () => {
        clearFieldError(identifierInput);
        hideStatusBanner(statusBanner);
      });
    }

    if (passwordInput) {
      passwordInput.addEventListener('input', () => {
        clearFieldError(passwordInput);
        hideStatusBanner(statusBanner);
      });
    }

    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      hideStatusBanner(statusBanner);
      let isValid = true;

      // 1. Validate Identifier (Username or Email)
      const identifierVal = identifierInput ? identifierInput.value.trim() : '';
      if (!identifierVal) {
        setFieldError(identifierInput, 'Username or email address is required.');
        isValid = false;
      } else {
        setFieldValid(identifierInput);
      }

      // 2. Validate Password
      const passwordVal = passwordInput ? passwordInput.value : '';
      if (!passwordVal) {
        setFieldError(passwordInput, 'Password is required.');
        isValid = false;
      } else {
        setFieldValid(passwordInput);
      }

      if (!isValid) {
        const firstInvalid = form.querySelector('.is-invalid');
        if (firstInvalid) firstInvalid.focus();
        return;
      }

      // Check API client availability
      if (!window.CyAwareAPI || !window.CyAwareAPI.login) {
        showStatusBanner(statusBanner, 'API service unavailable. Please check configuration.');
        return;
      }

      // Set Loading State
      const originalBtnHtml = submitBtn ? submitBtn.innerHTML : 'Sign In';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner" style="margin-right: 0.5rem;"></span> Signing In...';
      }

      try {
        const response = await window.CyAwareAPI.login({
          username_or_email: identifierVal,
          password: passwordVal
        });

        if (response && response.success) {
          if (window.CyAwareApp && window.CyAwareApp.showToast) {
            window.CyAwareApp.showToast('Login successful! Redirecting...', 'success');
          }
          // Redirect to authenticated dashboard workspace
          window.location.href = 'dashboard.html';
        } else {
          showStatusBanner(statusBanner, (response && response.message) || 'Login failed.');
        }
      } catch (err) {
        console.warn('Login failure:', err.code, err.message);

        let userMsg = err.message || 'An error occurred during sign in.';
        if (err.code === 'INVALID_CREDENTIALS') {
          userMsg = 'Invalid username/email or password.';
        } else if (err.code === 'ACCOUNT_DISABLED') {
          userMsg = 'This account has been deactivated. Please contact an administrator.';
        } else if (err.code === 'RATE_LIMITED' || err.status === 429) {
          userMsg = 'Too many failed login attempts. Please wait 5 minutes before trying again.';
        } else if (err.code === 'VALIDATION_ERROR') {
          userMsg = err.message || 'Please provide a valid username/email and password.';
        }

        showStatusBanner(statusBanner, userMsg, 'danger');
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast(userMsg, 'danger');
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHtml;
        }
      }
    });
  }

  // ==========================================================================
  // Registration Form Controller
  // ==========================================================================
  function initRegisterForm() {
    const form = document.getElementById('register-form');
    if (!form) return;

    const usernameInput = document.getElementById('register-username');
    const emailInput = document.getElementById('register-email');
    const passwordInput = document.getElementById('register-password');
    const confirmPasswordInput = document.getElementById('register-confirm-password');
    const termsCheck = document.getElementById('register-terms');
    const statusBanner = document.getElementById('register-status-banner');
    const submitBtn = form.querySelector('button[type="submit"]');

    if (usernameInput) {
      usernameInput.addEventListener('input', () => {
        clearFieldError(usernameInput);
        hideStatusBanner(statusBanner);
      });
      usernameInput.addEventListener('blur', function () {
        const val = this.value.trim();
        if (val && !isValidUsername(val)) {
          setFieldError(this, 'Username must be 3-30 characters long and contain only letters, numbers, and underscores.');
        } else if (val) {
          setFieldValid(this);
        }
      });
    }

    if (emailInput) {
      emailInput.addEventListener('input', () => {
        clearFieldError(emailInput);
        hideStatusBanner(statusBanner);
      });
      emailInput.addEventListener('blur', function () {
        const val = this.value.trim();
        if (val && !isValidEmail(val)) {
          setFieldError(this, 'Please enter a valid email address (e.g. user@example.com).');
        } else if (val) {
          setFieldValid(this);
        }
      });
    }

    if (passwordInput) {
      passwordInput.addEventListener('input', function () {
        clearFieldError(passwordInput);
        hideStatusBanner(statusBanner);
        updateStrengthMeter(this.value);

        if (confirmPasswordInput && confirmPasswordInput.value) {
          if (confirmPasswordInput.value !== this.value) {
            setFieldError(confirmPasswordInput, 'Passwords do not match.');
          } else {
            setFieldValid(confirmPasswordInput);
          }
        }
      });
    }

    if (confirmPasswordInput) {
      confirmPasswordInput.addEventListener('input', function () {
        clearFieldError(confirmPasswordInput);
        hideStatusBanner(statusBanner);
        if (passwordInput && this.value && this.value !== passwordInput.value) {
          setFieldError(this, 'Passwords do not match.');
        } else if (passwordInput && this.value && this.value === passwordInput.value) {
          setFieldValid(this);
        }
      });
    }

    if (termsCheck) {
      termsCheck.addEventListener('change', () => {
        clearFieldError(termsCheck);
        hideStatusBanner(statusBanner);
      });
    }

    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      hideStatusBanner(statusBanner);
      let isValid = true;

      // 1. Validate Username
      const usernameVal = usernameInput ? usernameInput.value.trim() : '';
      if (!usernameVal) {
        setFieldError(usernameInput, 'Username is required.');
        isValid = false;
      } else if (!isValidUsername(usernameVal)) {
        setFieldError(usernameInput, 'Username must be 3-30 characters long and contain only letters, numbers, and underscores.');
        isValid = false;
      } else {
        setFieldValid(usernameInput);
      }

      // 2. Validate Email
      const emailVal = emailInput ? emailInput.value.trim().toLowerCase() : '';
      if (!emailVal) {
        setFieldError(emailInput, 'Email address is required.');
        isValid = false;
      } else if (!isValidEmail(emailVal)) {
        setFieldError(emailInput, 'Please enter a valid email address.');
        isValid = false;
      } else {
        setFieldValid(emailInput);
      }

      // 3. Validate Password (backend requires: min 8 chars, >= 1 letter, >= 1 number)
      const passwordVal = passwordInput ? passwordInput.value : '';
      if (!passwordVal) {
        setFieldError(passwordInput, 'Password is required.');
        isValid = false;
      } else if (passwordVal.length < 8) {
        setFieldError(passwordInput, 'Password must be at least 8 characters long.');
        isValid = false;
      } else if (!/[a-zA-Z]/.test(passwordVal) || !/[0-9]/.test(passwordVal)) {
        setFieldError(passwordInput, 'Password must contain at least one letter and one number.');
        isValid = false;
      } else {
        setFieldValid(passwordInput);
      }

      // 4. Validate Confirm Password
      const confirmVal = confirmPasswordInput ? confirmPasswordInput.value : '';
      if (!confirmVal) {
        setFieldError(confirmPasswordInput, 'Please confirm your password.');
        isValid = false;
      } else if (confirmVal !== passwordVal) {
        setFieldError(confirmPasswordInput, 'Passwords do not match.');
        isValid = false;
      } else {
        setFieldValid(confirmPasswordInput);
      }

      // 5. Validate Terms Checkbox
      if (termsCheck && !termsCheck.checked) {
        setFieldError(termsCheck, 'You must acknowledge the Responsible AI Guidelines to register.');
        isValid = false;
      } else if (termsCheck) {
        clearFieldError(termsCheck);
      }

      if (!isValid) {
        const firstInvalid = form.querySelector('.is-invalid');
        if (firstInvalid) firstInvalid.focus();
        return;
      }

      // Check API client availability
      if (!window.CyAwareAPI || !window.CyAwareAPI.register) {
        showStatusBanner(statusBanner, 'API service unavailable. Please check configuration.');
        return;
      }

      // Set Loading State
      const originalBtnHtml = submitBtn ? submitBtn.innerHTML : 'Create Account';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner" style="margin-right: 0.5rem;"></span> Creating Account...';
      }

      try {
        const response = await window.CyAwareAPI.register({
          username: usernameVal,
          email: emailVal,
          password: passwordVal
        });

        if (response && response.success) {
          form.reset();
          if (usernameInput) clearFieldError(usernameInput);
          if (emailInput) clearFieldError(emailInput);
          if (passwordInput) clearFieldError(passwordInput);
          if (confirmPasswordInput) clearFieldError(confirmPasswordInput);

          const successMsg = 'Account created successfully! You can now sign in.';
          showStatusBanner(statusBanner, successMsg, 'success');

          // Append explicit login CTA button to banner
          statusBanner.innerHTML += `
            <div style="margin-top: 0.75rem;">
              <a href="login.html" class="btn btn-primary btn-sm" style="display: inline-block;">Proceed to Sign In</a>
            </div>
          `;

          if (window.CyAwareApp && window.CyAwareApp.showToast) {
            window.CyAwareApp.showToast('Account created successfully! Please sign in.', 'success');
          }
        } else {
          showStatusBanner(statusBanner, (response && response.message) || 'Registration failed.');
        }
      } catch (err) {
        console.warn('Registration failure:', err.code, err.message);

        let userMsg = err.message || 'An error occurred during account registration.';
        if (err.code === 'USER_EXISTS' || err.status === 409) {
          userMsg = 'Username or email is already registered. Please choose another or sign in.';
        } else if (err.code === 'VALIDATION_ERROR') {
          userMsg = err.message || 'Registration data is invalid. Please check your entries.';
        }

        showStatusBanner(statusBanner, userMsg, 'danger');
        if (window.CyAwareApp && window.CyAwareApp.showToast) {
          window.CyAwareApp.showToast(userMsg, 'danger');
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHtml;
        }
      }
    });
  }

  // Initialize on DOM ready
  document.addEventListener('DOMContentLoaded', function () {
    initPasswordToggles();
    initLoginForm();
    initRegisterForm();
  });
})();
