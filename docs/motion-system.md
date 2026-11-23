# LibriCore Motion System Architecture

## 1. Core Principles

Motion in LibriCore serves functional comprehension and spatial orientation. It does not exist for theatrical distraction or continuous looping decoration.

1. **Subtle and Purposeful**: Animations inform the reader of hierarchy, state transitions, or feedback to user interactions.
2. **Zero Delay to Action**: Interactive controls remain immediately responsive. Content is never hidden behind artificial loading delays.
3. **Progressive Enhancement**: All page content is 100% visible and interactive without JavaScript. If GSAP fails to load or execution is interrupted, the layout renders perfectly.
4. **Strict Accessibility**: Full honoring of `prefers-reduced-motion: reduce`. Animations gracefully bypass transforms and delays when reduced motion is requested.

---

## 2. Technical Architecture

- **Library**: GreenSock Animation Platform (GSAP 3.12.5) Core + ScrollTrigger 3.12.5.
- **Serving Strategy**: Pinned, locally hosted static vendor assets in `static/js/vendor/gsap.min.js` and `static/js/vendor/ScrollTrigger.min.js`.
- **Implementation File**: `static/js/motion.js`, cleanly decoupled from functional DOM logic in `static/js/main.js`.
- **Responsive Media Query Manager**: `gsap.matchMedia()` manages breakpoints and tear-down logic.

---

## 3. Motion Timing and Easing Tokens

| Token | Duration | Ease Function | Application |
| :--- | :--- | :--- | :--- |
| Quick Micro | 0.2s | `power2.out` | Button hovers, toggle switches |
| Enter Standard | 0.45s | `power3.out` | Card reveals, table row appearance |
| Orchestrated Sequence | 0.7s | `power3.out` | Landing hero sequence, banner reveal |
| Modal Transition | 0.3s | `power2.out` | Confirmation dialogs, mobile drawer |

---

## 4. Reusable Animation Patterns

### Pattern A: Hero Entrance Timeline
- Context: Landing page primary view.
- Sequence:
  1. Navbar subtly slides into position (`y: -12` to `0`, `opacity: 0` to `1`).
  2. Eyebrow badge fades in with slight upward drift (`y: 14` to `0`).
  3. Editorial hero headline reveals smoothly with staggered lines.
  4. Search bar and quick-category pills follow with a slight stagger (`0.08s`).
  5. Stat summary cards slide into place with a subtle elevation shift.

### Pattern B: ScrollTrigger Discovery
- Context: Landing page book showcase, workflow cards, policy blocks.
- Trigger: `start: "top 85%"`, `once: true`.
- Animation: Subtle upward drift (`y: 20` to `0`, `opacity: 0` to `1`) with stagger (`0.06s` to `0.1s`).
- Fallback: Content is visible by default (`opacity: 1`), animated only once ScrollTrigger initializes.

### Pattern C: Dashboard Entrance
- Context: Administrator, Librarian, and Member dashboards.
- Sequence:
  - Metric stat cards enter with a quick staggered fade (`0.05s` interval).
  - Main operational table or urgent alert panel enters with slight fade-in.
  - No continuous rotation or pulsing numbers that distract from administrative work.

### Pattern D: Modal and Drawer Transitions
- Modal: GSAP timeline triggers on `.modal-backdrop.active` animating `.modal-dialog` scale (`0.95` to `1`) and opacity (`0` to `1`).
- Drawer: GSAP controls mobile sidebar slide (`x: -100%` to `0`) and backdrop opacity.

### Pattern E: Editorial Reader Workspace Entrance
- Context: Member Personal Reading Desk.
- Sequence:
  - Archival Masthead reveals smoothly with subtle elevation (`y: 14` to `0`, `0.4s`).
  - Standing Ledger Strip cells cascade horizontally (`0.05s` stagger).
  - Editorial Workspace folios and Study Desk panels reveal in unified progression (`0.06s` stagger).

---

## 5. Responsive and Reduced-Motion Strategy

```javascript
const mm = gsap.matchMedia();

mm.add({
  isDesktop: "(min-width: 993px)",
  isMobile: "(max-width: 992px)",
  reduceMotion: "(prefers-reduced-motion: reduce)"
}, (context) => {
  const { isDesktop, reduceMotion } = context.conditions;

  if (reduceMotion) {
    // Keep transforms at 0, immediate rendering
    return;
  }

  // Desktop or Mobile appropriate choreographed sequences
});
```
