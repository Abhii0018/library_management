/**
 * GSAP 3.12.5 and ScrollTrigger motion system.
 * Uses matchMedia for viewport-specific choreography and honors prefers-reduced-motion.
 */

(function () {
  'use strict';

  if (typeof window === 'undefined') return;

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

      // Orchestrates hero elements entrance timeline.
      const heroContent = document.querySelector('.landing-hero-content');
      if (heroContent) {
        const heroTl = gsap.timeline({ defaults: { ease: 'power3.out' } });

        const heroNavbar = document.querySelector('.landing-navbar');
        if (heroNavbar) {
          heroTl.fromTo(heroNavbar, 
            { y: -16, opacity: 0 }, 
            { y: 0, opacity: 1, duration: 0.5 }
          );
        }

        const heroPill = heroContent.querySelector('.hero-pill');
        if (heroPill) {
          heroTl.fromTo(heroPill, 
            { y: 14, opacity: 0 }, 
            { y: 0, opacity: 1, duration: 0.4 }, 
            '-=0.2'
          );
        }

        const heroTitle = heroContent.querySelector('.hero-title');
        if (heroTitle) {
          heroTl.fromTo(heroTitle, 
            { y: 22, opacity: 0 }, 
            { y: 0, opacity: 1, duration: 0.65 }, 
            '-=0.25'
          );
        }

        const heroSubtitle = heroContent.querySelector('.hero-subtitle');
        if (heroSubtitle) {
          heroTl.fromTo(heroSubtitle, 
            { y: 18, opacity: 0 }, 
            { y: 0, opacity: 1, duration: 0.55 }, 
            '-=0.35'
          );
        }

        const heroSearch = heroContent.querySelector('.hero-search-box');
        if (heroSearch) {
          heroTl.fromTo(heroSearch, 
            { y: 20, opacity: 0, scale: 0.98 }, 
            { y: 0, opacity: 1, scale: 1, duration: 0.55 }, 
            '-=0.35'
          );
        }

        const categoryPills = heroContent.querySelectorAll('.landing-cat-tag');
        if (categoryPills.length > 0) {
          heroTl.fromTo(categoryPills, 
            { opacity: 0, y: 10 }, 
            { opacity: 1, y: 0, duration: 0.35, stagger: 0.03 }, 
            '-=0.3'
          );
        }

        const heroActions = heroContent.querySelector('.hero-actions');
        if (heroActions) {
          heroTl.fromTo(heroActions, 
            { opacity: 0, y: 14 }, 
            { opacity: 1, y: 0, duration: 0.45 }, 
            '-=0.25'
          );
        }

        const folioCard = document.querySelector('.curation-folio-card');
        if (folioCard) {
          heroTl.fromTo(folioCard,
            { y: 24, opacity: 0, scale: 0.96 },
            { y: 0, opacity: 1, scale: 1, duration: 0.7 },
            '-=0.4'
          );
        }

        const statsItems = document.querySelectorAll('.landing-stats-ledger .ledger-stat-item, .landing-stats-container .landing-stat-card');
        if (statsItems.length > 0) {
          heroTl.fromTo(statsItems, 
            { y: 24, opacity: 0 }, 
            { y: 0, opacity: 1, duration: 0.5, stagger: 0.08 }, 
            '-=0.2'
          );
        }
      }

      // Configures ScrollTrigger reveals for catalog cards and workflow sections.
      if (typeof ScrollTrigger !== 'undefined') {
        const bookCards = document.querySelectorAll('.books-grid .book-showcase-card');
        if (bookCards.length > 0) {
          gsap.fromTo(bookCards, 
            { opacity: 0, y: 28 }, 
            {
              opacity: 1,
              y: 0,
              duration: 0.55,
              stagger: 0.08,
              ease: 'power3.out',
              scrollTrigger: {
                trigger: '.books-grid',
                start: 'top 85%',
                once: true
              }
            }
          );
        }

        const workflowCards = document.querySelectorAll('.workflow-grid .workflow-card');
        if (workflowCards.length > 0) {
          gsap.fromTo(workflowCards, 
            { opacity: 0, y: 24 }, 
            {
              opacity: 1,
              y: 0,
              duration: 0.5,
              stagger: 0.1,
              ease: 'power3.out',
              scrollTrigger: {
                trigger: '.workflow-grid',
                start: 'top 85%',
                once: true
              }
            }
          );
        }

        const policyCards = document.querySelectorAll('.policy-grid .policy-card');
        if (policyCards.length > 0) {
          gsap.fromTo(policyCards, 
            { opacity: 0, y: 20 }, 
            {
              opacity: 1,
              y: 0,
              duration: 0.45,
              stagger: 0.08,
              ease: 'power3.out',
              scrollTrigger: {
                trigger: '.policy-grid',
                start: 'top 88%',
                once: true
              }
            }
          );
        }

        const banner = document.querySelector('.landing-banner');
        if (banner) {
          gsap.fromTo(banner, 
            { opacity: 0, y: 24, scale: 0.99 }, 
            {
              opacity: 1,
              y: 0,
              scale: 1,
              duration: 0.6,
              ease: 'power3.out',
              scrollTrigger: {
                trigger: banner,
                start: 'top 90%',
                once: true
              }
            }
          );
        }
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
