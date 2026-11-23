document.addEventListener('DOMContentLoaded', () => {
  const isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Navigation drawer toggling and mobile responsive handling.
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebarClose = document.getElementById('sidebarClose');
  const sidebarBackdrop = document.getElementById('sidebarBackdrop');
  const appSidebar = document.getElementById('appSidebar');

  const openSidebar = () => {
    document.body.classList.add('sidebar-open');
    if (sidebarToggle) sidebarToggle.setAttribute('aria-expanded', 'true');
  };

  const closeSidebar = () => {
    document.body.classList.remove('sidebar-open');
    if (sidebarToggle) sidebarToggle.setAttribute('aria-expanded', 'false');
  };

  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      if (document.body.classList.contains('sidebar-open')) {
        closeSidebar();
      } else {
        openSidebar();
      }
    });
  }

  if (sidebarClose) {
    sidebarClose.addEventListener('click', closeSidebar);
  }

  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener('click', closeSidebar);
  }

  window.addEventListener('resize', () => {
    if (window.innerWidth > 992 && document.body.classList.contains('sidebar-open')) {
      closeSidebar();
    }
  });

  // Notification alert dismissal handler.
  document.querySelectorAll('.alert-close').forEach(button => {
    button.addEventListener('click', () => {
      const alert = button.closest('.alert');
      if (alert) {
        if (isReducedMotion) {
          alert.remove();
        } else {
          alert.style.opacity = '0';
          alert.style.transform = 'translateY(-10px)';
          alert.addEventListener('transitionend', () => alert.remove(), { once: true });
          setTimeout(() => alert.remove(), 250);
        }
      }
    });
  });

  // Modal dialog for action confirmation.
  const modalBackdrop = document.getElementById('confirmModalBackdrop');
  const modalTitle = document.getElementById('confirmModalTitle');
  const modalMessage = document.getElementById('confirmModalMessage');
  const modalConfirmBtn = document.getElementById('confirmModalConfirm');
  const modalCancelBtn = document.getElementById('confirmModalCancel');
  const modalCloseBtn = document.getElementById('confirmModalClose');

  let pendingAction = null;
  let previousActiveElement = null;

  const showConfirmModal = (title, message, onConfirm) => {
    if (!modalBackdrop) {
      if (window.confirm(message)) onConfirm();
      return;
    }
    previousActiveElement = document.activeElement;
    pendingAction = onConfirm;
    if (modalTitle) modalTitle.textContent = title || 'Confirm Action';
    if (modalMessage) modalMessage.textContent = message || 'Are you sure you want to proceed?';

    modalBackdrop.classList.add('active');
    modalBackdrop.setAttribute('aria-hidden', 'false');
    if (modalConfirmBtn) modalConfirmBtn.focus();
  };

  const hideConfirmModal = () => {
    if (!modalBackdrop) return;
    modalBackdrop.classList.remove('active');
    modalBackdrop.setAttribute('aria-hidden', 'true');
    pendingAction = null;
    if (previousActiveElement && typeof previousActiveElement.focus === 'function') {
      previousActiveElement.focus();
    }
  };

  if (modalConfirmBtn) {
    modalConfirmBtn.addEventListener('click', () => {
      const action = pendingAction;
      hideConfirmModal();
      if (action) action();
    });
  }

  if (modalCancelBtn) modalCancelBtn.addEventListener('click', hideConfirmModal);
  if (modalCloseBtn) modalCloseBtn.addEventListener('click', hideConfirmModal);
  if (modalBackdrop) {
    modalBackdrop.addEventListener('click', (e) => {
      if (e.target === modalBackdrop) hideConfirmModal();
    });
  }

  // Event delegation for triggers with data-confirm attribute.
  document.addEventListener('click', (e) => {
    const trigger = e.target.closest('[data-confirm]');
    if (!trigger) return;

    if (trigger.getAttribute('data-confirmed') === 'true') {
      trigger.removeAttribute('data-confirmed');
      return;
    }

    e.preventDefault();
    const message = trigger.getAttribute('data-confirm');
    const title = trigger.getAttribute('data-confirm-title') || 'Confirmation Required';

    showConfirmModal(title, message, () => {
      trigger.setAttribute('data-confirmed', 'true');
      if (trigger.tagName === 'BUTTON' || trigger.tagName === 'INPUT') {
        const form = trigger.closest('form');
        if (form) {
          const hidden = document.createElement('input');
          hidden.type = 'hidden';
          hidden.name = trigger.name;
          hidden.value = trigger.value;
          form.appendChild(hidden);
          form.submit();
        } else {
          trigger.click();
        }
      } else if (trigger.tagName === 'A') {
        window.location.href = trigger.href;
      } else {
        trigger.click();
      }
    });
  });

  // Form submission handling to prevent duplicate POST requests.
  document.querySelectorAll('form').forEach(form => {
    if (form.method && form.method.toLowerCase() === 'post') {
      form.addEventListener('submit', (e) => {
        if (form.getAttribute('data-submitting') === 'true') {
          e.preventDefault();
          return;
        }

        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn && !submitBtn.hasAttribute('data-no-disable')) {
          form.setAttribute('data-submitting', 'true');
          submitBtn.classList.add('btn-submitting');
          submitBtn.disabled = true;

          // Timeout to re-enable submit button if response is delayed.
          setTimeout(() => {
            form.removeAttribute('data-submitting');
            submitBtn.classList.remove('btn-submitting');
            submitBtn.disabled = false;
          }, 8000);
        }
      });
    }
  });

  // Global keyboard handler for modal and drawer dismissal.
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (modalBackdrop && modalBackdrop.classList.contains('active')) {
        hideConfirmModal();
      } else if (document.body.classList.contains('sidebar-open')) {
        closeSidebar();
      } else {
        const openAlert = document.querySelector('.alert .alert-close');
        if (openAlert) openAlert.click();
      }
    }
  });
});
