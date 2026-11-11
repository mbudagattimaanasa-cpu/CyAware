/**
 * CyAware — Client-Side Authentication Form Validation
 * File: frontend/js/auth-validation.js
 * 
 * Implements Stage 2 requirements:
 * - Client-side validation: required fields, valid email regex, password matching, length checks.
 * - Password visibility toggle.
 * - Interactive validation feedback with accessible ARIA alerts.
 * - STRICT SEPARATION: No real authentication, no backend logic, no password storage, no invented API fields.
 */

(function () {
  'use strict';

  // Email format regex (RFC 5322 compliant basic pattern)
  const EMAIL_REGEX = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$/;

  // ==========================================================================
  // Validation Utilities
  // ==========================================================================
  function isValidEmail(email) {
    return EMAIL_REGEX.test(String(email).trim());
  }

  function setFieldError(field, errorMessage) {
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
    field.classList.remove('is-invalid');
    field.removeAttribute('aria-invalid');

    const errorContainer = document.getElementById(`${field.id}-error`);
    if (errorContainer) {
      errorContainer.textContent = '';
      errorContainer.style.display = 'none';
    }
  }

  function setFieldValid(field) {
    clearFieldError(field);
    field.classList.add('is-valid');
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

        // Update toggle icon
        if (isPassword) {
          // Eye-off icon
          this.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
              <line x1="1" y1="1" x2="23" y2="23"></line>
            </svg>
          `;
        } else {
          // Eye icon
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
    if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
    if (/[0-9]/.test(password) || /[^A-Za-z0-9]/.test(password)) score++;

    // Ensure non-empty passwords have at least score 1 (Weak)
    if (score === 0) {
      score = 1;
    }

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

    label.textContent = text ? `Strength: ${text}` : 'Minimum 8 characters with numbers or symbols';
  }

  // ==========================================================================
  // Login Form Controller
  // ==========================================================================
  function initLoginForm() {
    const form = document.getElementById('login-form');
    if (!form) return;

    const emailInput = document.getElementById('login-email');
    const passwordInput = document.getElementById('login-password');
    const statusBanner = document.getElementById('login-status-banner');

    // Real-time input cleanup
    if (emailInput) {
      emailInput.addEventListener('input', () => clearFieldError(emailInput));
      emailInput.addEventListener('blur', function () {
        const val = this.value.trim();
        if (val && !isValidEmail(val)) {
          setFieldError(this, 'Please enter a valid email address (e.g. user@example.com).');
        }
      });
    }

    if (passwordInput) {
      passwordInput.addEventListener('input', () => clearFieldError(passwordInput));
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      let isValid = true;

      // 1. Validate Email
      const emailVal = emailInput ? emailInput.value.trim() : '';
      if (!emailVal) {
        setFieldError(emailInput, 'Email address is required.');
        isValid = false;
      } else if (!isValidEmail(emailVal)) {
        setFieldError(emailInput, 'Please enter a valid email address.');
        isValid = false;
      } else {
        setFieldValid(emailInput);
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
        // Focus first invalid input
        const firstInvalid = form.querySelector('.is-invalid');
        if (firstInvalid) firstInvalid.focus();
        return;
      }

      // Stage 2 Demonstration Notice (No real authentication or backend request)
      if (statusBanner) {
        statusBanner.className = 'alert alert-info';
        statusBanner.style.display = 'flex';
        statusBanner.innerHTML = `
          <div class="alert-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="16" x2="12" y2="12"></line>
              <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
          </div>
          <div class="alert-content">
            <div class="alert-title">Stage 2 Validation Passed</div>
            <p style="margin: 0; font-size: 0.88rem;">
              Client-side credentials validation succeeded. As per Stage 2 separation rules, real network authentication targeting <code>POST /api/auth/login</code> will be connected in future integration stages.
            </p>
          </div>
        `;
      }

      if (window.CyAwareApp && window.CyAwareApp.showToast) {
        window.CyAwareApp.showToast('Login form validation succeeded (Stage 2 Demonstration).', 'success');
      }
    });
  }

  // ==========================================================================
  // Registration Form Controller
  // ==========================================================================
  function initRegisterForm() {
    const form = document.getElementById('register-form');
    if (!form) return;

    const nameInput = document.getElementById('register-name');
    const emailInput = document.getElementById('register-email');
    const passwordInput = document.getElementById('register-password');
    const confirmPasswordInput = document.getElementById('register-confirm-password');
    const termsCheck = document.getElementById('register-terms');
    const statusBanner = document.getElementById('register-status-banner');

    // Real-time input handlers
    if (nameInput) {
      nameInput.addEventListener('input', () => clearFieldError(nameInput));
    }

    if (emailInput) {
      emailInput.addEventListener('input', () => clearFieldError(emailInput));
      emailInput.addEventListener('blur', function () {
        const val = this.value.trim();
        if (val && !isValidEmail(val)) {
          setFieldError(this, 'Please enter a valid email address (e.g. user@example.com).');
        }
      });
    }

    if (passwordInput) {
      passwordInput.addEventListener('input', function () {
        clearFieldError(passwordInput);
        updateStrengthMeter(this.value);

        // Also re-validate confirmation if already typed
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
        if (passwordInput && this.value && this.value !== passwordInput.value) {
          setFieldError(this, 'Passwords do not match.');
        } else if (passwordInput && this.value && this.value === passwordInput.value) {
          setFieldValid(this);
        }
      });
    }

    if (termsCheck) {
      termsCheck.addEventListener('change', () => clearFieldError(termsCheck));
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      let isValid = true;

      // 1. Validate Name
      const nameVal = nameInput ? nameInput.value.trim() : '';
      if (!nameVal) {
        setFieldError(nameInput, 'Full name is required.');
        isValid = false;
      } else if (nameVal.length < 2) {
        setFieldError(nameInput, 'Name must be at least 2 characters long.');
        isValid = false;
      } else {
        setFieldValid(nameInput);
      }

      // 2. Validate Email
      const emailVal = emailInput ? emailInput.value.trim() : '';
      if (!emailVal) {
        setFieldError(emailInput, 'Email address is required.');
        isValid = false;
      } else if (!isValidEmail(emailVal)) {
        setFieldError(emailInput, 'Please enter a valid email address.');
        isValid = false;
      } else {
        setFieldValid(emailInput);
      }

      // 3. Validate Password
      const passwordVal = passwordInput ? passwordInput.value : '';
      if (!passwordVal) {
        setFieldError(passwordInput, 'Password is required.');
        isValid = false;
      } else if (passwordVal.length < 8) {
        setFieldError(passwordInput, 'Password must be at least 8 characters long.');
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

      // Stage 2 Demonstration Notice (No real registration or database storage)
      if (statusBanner) {
        statusBanner.className = 'alert alert-info';
        statusBanner.style.display = 'flex';
        statusBanner.innerHTML = `
          <div class="alert-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="16" x2="12" y2="12"></line>
              <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
          </div>
          <div class="alert-content">
            <div class="alert-title">Stage 2 Validation Passed</div>
            <p style="margin: 0 0 0.5rem 0; font-size: 0.88rem;">
              Registration fields are fully valid. Real account registration via <code>POST /api/auth/register</code> will be hooked up in future backend integration.
            </p>
            <a href="login.html" class="btn btn-primary btn-sm" style="display: inline-block;">Proceed to Sign In</a>
          </div>
        `;
      }

      if (window.CyAwareApp && window.CyAwareApp.showToast) {
        window.CyAwareApp.showToast('Registration validation succeeded (Stage 2 Demonstration).', 'success');
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

