# Design Tokens

## Compact summary

- Primary navy: `#163d6b`; deep navy: `#081525`; gold accent: `#d97706` / `#fbbf24`
- Main background: `#f8fafc`; card: `#ffffff`; text: `#0f172a`; muted: `#64748b`
- Fonts: Plus Jakarta Sans; display accents use Playfair Display where needed
- Radii: 4px, 8px, 12px, 18px, 24px, 9999px
- Shadows: subtle card shadows through floating 20px+ shadows
- Breakpoints: 992px, 860px, 640px
- Motion: cubic-bezier(0.4, 0, 0.2, 1), short transitions around 220ms

## Source

```css
:root {
  --primary: #163d6b;
  --gold: #d97706;
  --bg-main: #f8fafc;
  --bg-card: #ffffff;
  --text-main: #0f172a;
  --text-muted: #64748b;
  --radius-md: 12px;
  --radius-lg: 18px;
  --radius-full: 9999px;
}
```
