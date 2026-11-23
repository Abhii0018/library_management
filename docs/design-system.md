# LibriCore Design System: Scholarly Athenaeum

## 1. Visual Direction and Philosophy

LibriCore embodies the Scholarly Athenaeum design identity. It unites the gravitas of classical research archives with modern digital product ergonomics. The aesthetic avoids generic SaaS defaults (such as purple gradient washes, arbitrary rounded card clusters, and glassmorphic blur) in favor of structured architectural geometry, disciplined typography, and rich archival contrast.

### Core Visual Principles

1. **Archival Substance**: Solid structural divisions, fine brass-rule separators, and tactile catalog borders replace diffuse drop shadows and arbitrary neon highlights.
2. **Editorial Typographic Hierarchy**: Major headings employ an authoritative serif display face (Playfair Display) reminiscent of academic monographs. Interactive elements and dense data use an exceptionally legible sans-serif (Plus Jakarta Sans) and tabular numerals.
3. **Purposeful Density**: Administrative and circulation dashboards prioritize actionable operational throughput. Reader-facing surfaces prioritize calm discovery, legible reading metrics, and straightforward borrowing actions.
4. **Restraint Over Novelty**: Motion and decoration never obscure data or delay user tasks.

---

## 2. Color Palette and Semantic Tokens

The palette is derived from deep archival morocco leather, architectural navy, parchment stone, and burnished brass.

### Primary Tokens

| Token Name | Hex Value | Role |
| :--- | :--- | :--- |
| `--navy-deep` | `#081525` | Deep institutional base, sidebar navigation, dark text headings |
| `--navy-academic` | `#122c4d` | Core brand identity, primary buttons, hero surface |
| `--brass-gold` | `#c29337` | Athenaeum accent, active states, focus indicators, badges |
| `--parchment-bg` | `#f8f9fa` | Application canvas background |
| `--surface-card` | `#ffffff` | Elevated data cards, tables, inspection panels |
| `--border-rule` | `#e2e8f0` | Architectural dividers, fine borders, grid outlines |
| `--text-ink` | `#0f172a` | High-contrast editorial body text |
| `--text-subtle` | `#5a6878` | Secondary labels, metadata, ISBNs, timestamps |

### Functional Status Tokens

| Token Name | Hex Value | Role |
| :--- | :--- | :--- |
| `--status-available` | `#0f766e` | Shelf availability, approved requests, completed loans |
| `--status-due` | `#b45309` | Active loans, pending librarian reviews |
| `--status-overdue` | `#be123c` | Overdue loans, unpaid penalties, blocked status |

---

## 3. Typography Architecture

### Font Families

- **Display & Editorial Headings**: `Playfair Display`, Georgia, serif.
- **Interface & System Content**: `Plus Jakarta Sans`, system-ui, -apple-system, sans-serif.
- **Tabular & Monospace Identifiers**: `ui-monospace`, `SFMono-Regular`, `Menlo`, monospace with `font-variant-numeric: tabular-nums`.

### Type Scale

| Element | Size | Weight | Line Height | Tracking | Family |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Hero Display | 44px - 56px | 700 | 1.15 | -0.02em | Playfair Display |
| Page Heading (H1) | 28px - 34px | 700 | 1.25 | -0.015em | Playfair Display |
| Section Title (H2) | 22px - 26px | 600 | 1.3 | -0.01em | Plus Jakarta Sans / Playfair |
| Card Title (H3) | 16px - 18px | 600 | 1.4 | 0 | Plus Jakarta Sans |
| Body Regular | 14.5px | 400 / 500 | 1.55 | 0 | Plus Jakarta Sans |
| Small / Metadata | 12px - 13px | 500 / 600 | 1.45 | 0.02em | Plus Jakarta Sans / Mono |

---

## 4. Layout and Spatial Geometry

- **Container Max Width**: 1280px for landing and broad catalog; 1400px for high-density administrative master views.
- **Grid Systems**:
  - Stats Grid: 3 to 4 auto-fit columns (`minmax(240px, 1fr)`).
  - Editorial Book Grid: 3 columns (`minmax(300px, 1fr)`) with asymmetric feature hero card.
  - Form Layouts: Strict two-column aligned fieldsets (`form-grid-2`) with 20px gutter.
- **Radii Standards**:
  - Small elements (badges, buttons, search inputs): 6px to 8px.
  - Large containers (cards, modals, drawer): 10px to 14px.
  - Pill tags: 9999px.

---

## 5. Component Specifications

### Buttons
- **Primary**: Deep academic navy (`--navy-academic`) with smooth background transition to `#0c2340`, gold focus ring.
- **Secondary**: Clean parchment slate with `#e2e8f0` border, transitions to `#f1f5f9` on hover.
- **Success / Danger Actions**: Solid background fills with high-contrast white text for immediate operational clarity.

### Catalog Cards
- Modeled after academic archival folios.
- Top spine marker with book category pill.
- Real-time stock status badge with tabular copy counts.
- High-contrast direct action buttons (`View Details`, `Request`).

### Tables and Ledgers
- Fine horizontal dividers (`1px solid var(--border-rule)`).
- Subtly tinted header row with uppercase metadata labels.
- Right-aligned tabular numeric data (dates, durations, currencies).

---

## 6. Contemporary Editorial Digital Archive Components

### Reader Masthead (`.archival-masthead`)
- Deep navy linear gradient with subtle gold radial glow and gold border rule.
- Displays academic member identity, registry chip (MEM-ID), and clearance status.
- Integrates primary discovery and ledger access shortcuts.

### Standing Ledger Strip (`.standing-ledger-strip`)
- 4-column connected architectural metric ledger replacing disconnected floating cards.
- Integrates real-time borrowing quota gauge with progress rule, requisition queue count, overdue audit counter, and outstanding fee balance.

### Asymmetrical Reader Workspace (`.editorial-layout`)
- Two-column split: 68% primary reading workspace and 32% study desk sidebar.
- Primary workspace houses active loan folios with tactile spine indicators, curated archival stacks for immediate discovery, and requisition status ledger.
- Study desk sidebar encapsulates institutional circulation code, direct registry navigation, and recent loan history snippets.

### Active Loan Folios (`.loan-folio`)
- Horizontal archival folio cards featuring spine accent indicator (navy for standard, red for overdue).
- Displays category tag, shelf mark, ISBN, title in Playfair Display, issue date, due date, accrued fees, and countdown status pills.

### Archival Empty State (`.archival-empty-panel`)
- Replaces generic blank table states with an intentional editorial reading desk invitation.
- Provides immediate call to action to discover curated volumes in the catalog.
