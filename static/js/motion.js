/**
 * GSAP 3.12.5 and ScrollTrigger motion system.
 * Uses matchMedia for viewport-specific choreography and honors prefers-reduced-motion.
 */

(function () {
  'use strict';

  if (typeof window === 'undefined') return;

  /**
   * Counts pure-integer text nodes up from zero. Non-numeric values (currency,
   * ratios) are left untouched so nothing is ever displayed incorrectly.
   */
  function countUp(nodes, options) {
    const settings = Object.assign({ duration: 1.4, delay: 0 }, options);
    Array.from(nodes).forEach((node) => {
      const raw = node.textContent.trim();
      if (!/^\d{1,9}$/.test(raw)) return;
      const end = parseInt(raw, 10);
      if (end === 0) return;
      const state = { value: 0 };
      node.textContent = '0';
      gsap.to(state, {
        value: end,
        duration: settings.duration,
        delay: settings.delay,
        ease: 'power2.out',
        snap: { value: 1 },
        onUpdate: () => { node.textContent = String(state.value); },
        onComplete: () => { node.textContent = String(end); }
      });
    });
  }

  window.LibriMotion = { countUp: countUp };

  function initMotion() {
    if (typeof gsap === 'undefined') {
      return;
    }

    if (typeof ScrollTrigger !== 'undefined') {
      gsap.registerPlugin(ScrollTrigger);
    }

    const mm = gsap.matchMedia();

    mm.add({
      isDesktop: '(min-width: 993px)',
      isMobile: '(max-width: 992px)',
      reduceMotion: '(prefers-reduced-motion: reduce)'
    }, (context) => {
      const { isDesktop, reduceMotion } = context.conditions;

      if (reduceMotion) {
        return;
      }

      // Animates dashboard topbar and metric card entries.
      const appMain = document.querySelector('.app-main');
      if (appMain) {
        const dashTl = gsap.timeline({ defaults: { ease: 'power2.out' } });

        const topbar = document.querySelector('.app-topbar');
        if (topbar) {
          dashTl.fromTo(topbar, 
            { opacity: 0, y: -10 }, 
            { opacity: 1, y: 0, duration: 0.35 }
          );
        }

        const archivalMasthead = document.querySelector('.archival-masthead');
        if (archivalMasthead) {
          dashTl.fromTo(archivalMasthead,
            { opacity: 0, y: 14 },
            { opacity: 1, y: 0, duration: 0.4 },
            '-=0.15'
          );
        }

        const standingCells = document.querySelectorAll('.standing-ledger-strip .standing-cell');
        if (standingCells.length > 0) {
          dashTl.fromTo(standingCells,
            { opacity: 0, y: 12 },
            { opacity: 1, y: 0, duration: 0.35, stagger: 0.05 },
            '-=0.2'
          );
        }

        const statCards = document.querySelectorAll('.stats-grid .stat-card');
        if (statCards.length > 0) {
          dashTl.fromTo(statCards, 
            { opacity: 0, y: 16 }, 
            { opacity: 1, y: 0, duration: 0.4, stagger: 0.05 }, 
            '-=0.15'
          );
        }

        const editorialCards = document.querySelectorAll('.editorial-workspace > *, .editorial-sidebar > *');
        if (editorialCards.length > 0) {
          dashTl.fromTo(editorialCards,
            { opacity: 0, y: 14 },
            { opacity: 1, y: 0, duration: 0.4, stagger: 0.06 },
            '-=0.2'
          );
        }

        const contentCards = document.querySelectorAll('.content-body > .card, .content-body > .toolbar-container, .content-body > .grid-2');
        if (contentCards.length > 0) {
          dashTl.fromTo(contentCards, 
            { opacity: 0, y: 14 }, 
            { opacity: 1, y: 0, duration: 0.45, stagger: 0.08 }, 
            '-=0.2'
          );
        }
      }

      if (appMain) {
        countUp(document.querySelectorAll('.standing-num, .stat-value'), { delay: 0.35 });
      }

      // Observes modal visibility mutations to trigger entrance transitions.
      const modalBackdrop = document.getElementById('confirmModalBackdrop');
      if (modalBackdrop) {
        const observer = new MutationObserver((mutations) => {
          mutations.forEach((mutation) => {
            if (mutation.attributeName === 'class') {
              const isActive = modalBackdrop.classList.contains('active');
              const modalDialog = modalBackdrop.querySelector('.modal-dialog');
              if (modalDialog) {
                if (isActive) {
                  gsap.fromTo(modalDialog, 
                    { scale: 0.94, opacity: 0, y: 12 }, 
                    { scale: 1, opacity: 1, y: 0, duration: 0.28, ease: 'power3.out' }
                  );
                } else {
                  gsap.set(modalDialog, { clearProps: 'all' });
                }
              }
            }
          });
        });

        observer.observe(modalBackdrop, { attributes: true });
      }

    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMotion);
  } else {
    initMotion();
  }
})();
