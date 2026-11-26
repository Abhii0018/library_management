/**
 * Landing page choreography: living shelf, SplitText headlines, velocity ticker,
 * pinned loan lifecycle on a MotionPath. All motion lives inside gsap.matchMedia()
 * so reduced-motion users get the static page; content is visible by default.
 */
(function () {
  'use strict';

  if (typeof gsap === 'undefined' || !document.querySelector('.landing-hero')) return;

  const root = document.documentElement;
  const plugins = ['ScrollTrigger', 'SplitText', 'MotionPathPlugin', 'DrawSVGPlugin']
    .map((name) => window[name])
    .filter(Boolean);
  gsap.registerPlugin.apply(gsap, plugins);
  const has = (name) => Boolean(window[name]);
  const reveal = () => root.classList.add('motion-ready');

  const state = { paused: false };

  function stampDueDate() {
    const stamp = document.getElementById('dueStamp');
    if (!stamp) return;
    const due = new Date();
    due.setDate(due.getDate() + Number(stamp.dataset.dueDays || 14));
    stamp.textContent = 'Due ' + due.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  function init() {
    stampDueDate();

    const mm = gsap.matchMedia();
    mm.add({
      isMotion: '(prefers-reduced-motion: no-preference)',
      isDesktop: '(min-width: 993px) and (min-height: 780px)',
      isWide: '(min-width: 993px)',
      canHover: '(hover: hover) and (pointer: fine)'
    }, (context) => {
      const { isMotion, isDesktop, isWide, canHover } = context.conditions;
      if (!isMotion) {
        reveal();
        return undefined;
      }

      const cleanups = [];
      const q = (selector, scope) => (scope || document).querySelector(selector);
      const qa = (selector, scope) => Array.from((scope || document).querySelectorAll(selector));

      // Scroll progress hairline in the navbar.
      if (has('ScrollTrigger') && q('.landing-progress')) {
        gsap.to('.landing-progress', {
          scaleX: 1,
          ease: 'none',
          scrollTrigger: { start: 0, end: 'max', scrub: 0.3 }
        });
      }

      // Hero entrance.
      const hero = gsap.timeline({ defaults: { ease: 'expo.out' } });
      hero
        .fromTo('.landing-navbar', { yPercent: -100 }, { yPercent: 0, duration: 0.8, ease: 'power3.out', clearProps: 'transform' }, 0)
        .fromTo('.hero-pill',
          { opacity: 0, y: 10, transition: 'none' },
          { opacity: 1, y: 0, duration: 0.7, clearProps: 'opacity,transform,transition' },
          0.15);

      if (has('SplitText') && q('.hero-title')) {
        SplitText.create('.hero-title', {
          type: 'lines',
          mask: 'lines',
          autoSplit: true,
          onSplit(self) {
            reveal();
            const tl = gsap.timeline({ delay: 0.2 });
            tl.from(self.lines, { yPercent: 115, duration: 1.1, ease: 'expo.out', stagger: 0.12 }, 0);
            const accents = self.elements[0].querySelectorAll('span');
            if (accents.length) {
              tl.fromTo(accents, { '--underline': 0 }, { '--underline': 1, duration: 0.9, ease: 'power3.inOut' }, 0.95);
            }
            return tl;
          }
        });
      } else {
        reveal();
      }

      if (has('SplitText') && q('.hero-subtitle')) {
        SplitText.create('.hero-subtitle', {
          type: 'lines',
          mask: 'lines',
          autoSplit: true,
          onSplit(self) {
            return gsap.from(self.lines, { yPercent: 110, duration: 0.9, ease: 'expo.out', stagger: 0.08, delay: 0.55 });
          }
        });
      }

      hero
        .fromTo('.hero-search-box',
          { clipPath: 'inset(0% 100% 0% 0% round 999px)' },
          { clipPath: 'inset(0% 0% 0% 0% round 999px)', duration: 1.1, ease: 'expo.inOut', clearProps: 'clipPath' },
          0.85)
        .fromTo('.landing-cat-tag',
          { opacity: 0, y: 12, scale: 0.96, transition: 'none' },
          { opacity: 1, y: 0, scale: 1, duration: 0.5, stagger: 0.035, ease: 'power3.out', clearProps: 'opacity,transform,transition' },
          1.25)
        .fromTo('.hero-actions > *',
          { opacity: 0, y: 12, transition: 'none' },
          { opacity: 1, y: 0, duration: 0.6, stagger: 0.08, ease: 'power3.out', clearProps: 'opacity,transform,transition' },
          1.5);

      // Living shelf.
      const stage = isWide ? q('#shelfStage') : null;
      if (stage) {
        const shelfCase = q('.shelf-case', stage);
        const slip = q('.due-slip', stage);
        const stamp = q('.due-stamp', stage);
        const spines = qa('.spine', stage);

        gsap.set(spines, { transformOrigin: '50% 100%' });
        hero
          .from(qa('.shelf-plank', stage), { scaleX: 0, duration: 1, stagger: 0.14, ease: 'expo.out' }, 0.45)
          .from(spines, {
            y: -110,
            rotation: () => gsap.utils.random(-16, 16),
            opacity: 0,
            duration: 1,
            ease: 'back.out(1.4)',
            stagger: { each: 0.03, from: 'random' }
          }, 0.75)
          .from(slip, { y: 70, opacity: 0, rotation: -14, duration: 0.9, ease: 'power3.out' }, 1.7);

        if (stamp) {
          hero
            .from(stamp, { scale: 2.6, rotation: -26, opacity: 0, duration: 0.22, ease: 'power4.in' }, 2.35)
            .to(slip, { x: -3, duration: 0.05, yoyo: true, repeat: 3, ease: 'power1.inOut' }, 2.57);
        }

        // Idle: one random real spine lifts out and slides back every few seconds.
        let idle;
        const pull = () => {
          if (!state.paused && !document.hidden) {
            const links = qa('.spine-link', stage);
            if (links.length) {
              const el = gsap.utils.random(links);
              if (!el.matches(':hover')) {
                gsap.to(el, { y: -16, duration: 0.45, ease: 'power2.out', yoyo: true, repeat: 1 });
              }
            }
          }
          idle = gsap.delayedCall(3.4, pull);
        };
        idle = gsap.delayedCall(5, pull);
        cleanups.push(() => idle.kill());

        if (canHover && shelfCase) {
          gsap.set(shelfCase, { transformPerspective: 900 });
          const rotY = gsap.quickTo(shelfCase, 'rotationY', { duration: 0.8, ease: 'power3' });
          const rotX = gsap.quickTo(shelfCase, 'rotationX', { duration: 0.8, ease: 'power3' });
          const slipX = gsap.quickTo(slip, 'xPercent', { duration: 1, ease: 'power3' });
          const onMove = (event) => {
            const box = stage.getBoundingClientRect();
            const px = (event.clientX - box.left) / box.width - 0.5;
            const py = (event.clientY - box.top) / box.height - 0.5;
            rotY(px * 9);
            rotX(py * -7);
            slipX(px * -12);
          };
          const onLeave = () => { rotY(0); rotX(0); slipX(0); };
          stage.addEventListener('pointermove', onMove);
          stage.addEventListener('pointerleave', onLeave);
          cleanups.push(() => {
            stage.removeEventListener('pointermove', onMove);
            stage.removeEventListener('pointerleave', onLeave);
          });
        }
      }

      // Holdings ledger count-up. Final values are restored if this branch reverts.
      if (has('ScrollTrigger') && window.LibriMotion) {
        const numbers = qa('.ledger-stat-num');
        numbers.forEach((node) => {
          node.dataset.final = node.textContent.trim();
          if (/^\d+$/.test(node.dataset.final) && node.dataset.final !== '0') node.textContent = '0';
        });
        cleanups.push(() => numbers.forEach((node) => { node.textContent = node.dataset.final; }));
        ScrollTrigger.create({
          trigger: '.landing-stats-ledger',
          start: 'top 92%',
          once: true,
          onEnter: () => {
            numbers.forEach((node) => { node.textContent = node.dataset.final; });
            window.LibriMotion.countUp(numbers, { duration: 1.6 });
          }
        });
        hero.fromTo('.ledger-stat-item',
          { y: 30, opacity: 0, transition: 'none' },
          { y: 0, opacity: 1, duration: 0.7, stagger: 0.08, ease: 'power3.out', clearProps: 'opacity,transform,transition' },
          1.9);
      }

      // Ticker pause toggle control and scroll acceleration (WCAG 2.2.2).
      const track = q('#tickerTrack');
      if (track) {
        const toggle = q('#motionToggle');
        if (toggle) {
          const onToggle = () => {
            state.paused = !state.paused;
            track.classList.toggle('is-paused', state.paused);
            toggle.setAttribute('aria-pressed', String(state.paused));
            toggle.textContent = state.paused ? 'Resume motion' : 'Pause motion';
          };
          toggle.addEventListener('click', onToggle);
          cleanups.push(() => {
            toggle.removeEventListener('click', onToggle);
            toggle.setAttribute('aria-pressed', 'false');
            toggle.textContent = 'Pause motion';
            track.classList.remove('is-paused');
            state.paused = false;
          });
        }
      }

      // Section headlines: line mask rise on scroll.
      if (has('SplitText') && has('ScrollTrigger')) {
        qa('.section-title').forEach((title) => {
          SplitText.create(title, {
            type: 'lines',
            mask: 'lines',
            autoSplit: true,
            onSplit(self) {
              return gsap.from(self.lines, {
                yPercent: 110,
                duration: 1,
                ease: 'expo.out',
                stagger: 0.1,
                scrollTrigger: { trigger: title, start: 'top 86%', once: true }
              });
            }
          });
        });
      }

      // Cards slide out of a slot, then tilt toward the pointer.
      if (has('ScrollTrigger')) {
        const slot = (targets, trigger, start) => {
          if (!targets.length) return;
          gsap.fromTo(targets,
            { clipPath: 'inset(100% 0% 0% 0%)', y: 36 },
            {
              clipPath: 'inset(0% 0% 0% 0%)',
              y: 0,
              duration: 0.95,
              ease: 'expo.out',
              stagger: 0.09,
              clearProps: 'clipPath',
              scrollTrigger: { trigger, start, once: true }
            });
        };
        slot(qa('.books-grid .book-showcase-card'), '.books-grid', 'top 84%');
        slot(qa('.policy-grid .policy-card'), '.policy-grid', 'top 88%');
        slot(qa('.landing-banner'), '.landing-banner', 'top 92%');
      }

      if (canHover) {
        qa('.book-showcase-card').forEach((card) => {
          gsap.set(card, { transformPerspective: 900, transition: 'box-shadow 0.3s ease, border-color 0.3s ease' });
          const rotY = gsap.quickTo(card, 'rotationY', { duration: 0.6, ease: 'power3' });
          const rotX = gsap.quickTo(card, 'rotationX', { duration: 0.6, ease: 'power3' });
          const onMove = (event) => {
            const box = card.getBoundingClientRect();
            rotY(((event.clientX - box.left) / box.width - 0.5) * 7);
            rotX(((event.clientY - box.top) / box.height - 0.5) * -7);
          };
          const onLeave = () => { rotY(0); rotX(0); };
          card.addEventListener('pointermove', onMove);
          card.addEventListener('pointerleave', onLeave);
          cleanups.push(() => {
            card.removeEventListener('pointermove', onMove);
            card.removeEventListener('pointerleave', onLeave);
            gsap.set(card, { clearProps: 'transform,transition' });
          });
        });

        qa('.hero-action-join, .hero-action-browse, .btn-catalog-all, .banner-btn, .banner-btn-alt').forEach((button) => {
          const moveX = gsap.quickTo(button, 'x', { duration: 0.5, ease: 'power3' });
          const moveY = gsap.quickTo(button, 'y', { duration: 0.5, ease: 'power3' });
          const onMove = (event) => {
            const box = button.getBoundingClientRect();
            moveX((event.clientX - (box.left + box.width / 2)) * 0.22);
            moveY((event.clientY - (box.top + box.height / 2)) * 0.3);
          };
          const onLeave = () => { moveX(0); moveY(0); };
          button.addEventListener('pointermove', onMove);
          button.addEventListener('pointerleave', onLeave);
          cleanups.push(() => {
            button.removeEventListener('pointermove', onMove);
            button.removeEventListener('pointerleave', onLeave);
            gsap.set(button, { clearProps: 'transform' });
          });
        });
      }

      // The single pinned scene: a book travels the loan lifecycle on a MotionPath.
      const lifecycle = q('#how-it-works');
      if (isDesktop && lifecycle && has('ScrollTrigger') && has('MotionPathPlugin') && has('DrawSVGPlugin') && q('#lifecyclePath')) {
        const cards = qa('.workflow-card', lifecycle);
        const mark = (index, on) => { if (cards[index]) cards[index].classList.toggle('is-reached', on); };
        lifecycle.classList.add('has-lifecycle');
        mark(0, true);

        const journey = gsap.timeline({
          defaults: { ease: 'none' },
          scrollTrigger: {
            trigger: lifecycle,
            start: 'top 70px',
            end: '+=1300',
            pin: true,
            scrub: 0.6,
            anticipatePin: 1,
            onUpdate: (self) => {
              mark(1, self.progress >= 0.5);
              mark(2, self.progress >= 0.98);
            }
          }
        });
        journey
          .fromTo('#lifecyclePath', { drawSVG: '0%' }, { drawSVG: '100%' }, 0)
          .to('#lifecycleBook', {
            motionPath: { path: '#lifecyclePath', align: '#lifecyclePath', alignOrigin: [0.5, 0.5] }
          }, 0);

        cleanups.push(() => {
          lifecycle.classList.remove('has-lifecycle');
          cards.forEach((card) => card.classList.remove('is-reached'));
        });
      }

      return () => cleanups.forEach((fn) => fn());
    });

    if (has('ScrollTrigger')) {
      const refresh = () => ScrollTrigger.refresh();
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(refresh);
      window.addEventListener('load', refresh);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
