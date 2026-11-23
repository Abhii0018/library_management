# LibriCore Curated Library Catalogue Expansion and Data Population Report

## 1. Executive Summary

The LibriCore catalogue has been enriched from an initial seed of 7 books to a curated, high-integrity academic collection of 90 titles. The bibliographic data represents genuine, published monographs across 10 academic disciplines.

Each record includes verified ISBNs, publishers, publication dates, academic edition details, language codes, accurate page counts, Dewey-inspired shelf classifications, replacement valuations, and authoritative synopses.

---

## 2. Bibliographic Schema Enhancements

The `Book` model (`books/models.py`) was enhanced with six optional metadata fields to support academic monograph cataloguing while maintaining backward compatibility with existing records:

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `publisher` | `CharField(max_length=255)` | `blank=True, default=''` | Publishing house or academic press |
| `publication_year` | `PositiveIntegerField` | `null=True, blank=True` | Monograph copyright or publication year |
| `edition` | `CharField(max_length=64)` | `blank=True, default=''` | Edition designation (e.g. 3rd Edition, Revised) |
| `language` | `CharField(max_length=32)` | `default='English'` | Language of the physical volume |
| `page_count` | `PositiveIntegerField` | `null=True, blank=True` | Number of catalogued pages |
| `cover_image` | `CharField(max_length=255)` | `blank=True, default=''` | Relative static path to cover asset |

### Database Migrations
Migration `books/migrations/0003_book_cover_image_book_edition_book_language_and_more.py` applied these columns without table rebuilds or data loss. All existing records (such as initial circulation test loans) retain their loan history, copy quantities, and status.

---

## 3. Curated Catalogue Distribution

The catalogue comprises 90 distinct volumes distributed across 10 academic disciplines:

| Discipline | Total Titles | Representative Works |
| :--- | :--- | :--- |
| Computer Science | 9 | SICP, Introduction to Algorithms, Clean Code, Compilers |
| Mathematics | 9 | Principles of Mathematical Analysis, Topology, Abstract Algebra |
| Physics | 9 | Feynman Lectures, Quantum Mechanics, Classical Mechanics |
| Biology | 9 | Molecular Biology of the Cell, Origin of Species, Lehninger |
| Chemistry | 9 | Central Science, Organic Chemistry, Physical Chemistry |
| History & Politics | 9 | Sapiens, The Guns of August, Leviathan, The Prince |
| Philosophy | 9 | Republic, Critique of Pure Reason, Beyond Good and Evil |
| Literature & Fiction | 9 | 1984, To Kill a Mockingbird, Crime and Punishment, Ulysses |
| Economics | 9 | Wealth of Nations, Capital, General Theory, Thinking Fast & Slow |
| Engineering | 9 | Roark's Formulas, Electric Machinery, Art of Electronics |
| **Total** | **90** | **Balanced academic foundation** |

---

## 4. Visual Assets and Cover Handling

Cover art is managed locally within the Django static directory (`static/images/covers/`):

- **Local Cover JPEGs**: 46 verified high-resolution cover images retrieved from Open Library Archives and cached locally.
- **Typographic Fallbacks**: 44 titles utilize an institutional SVG folio fallback with academic iconography, eliminating broken external image requests or layout shifting.
- **Zero Heavy C-Extensions**: `cover_image` stores the relative static asset path rather than requiring Pillow runtime image compilation, ensuring fast startup across WSL and serverless containers.

---

## 5. Management Command and Idempotency

The catalogue is populated via an idempotent management command:

```bash
uv run python manage.py seed_catalog
```

### Supported Flags
- `--dry-run`: Simulates the insertion and enrichment without committing changes to SQLite or MongoDB.
- `--dataset`: Specifies a custom JSON dataset file path (defaults to `books/data/catalog_dataset.json`).

### Idempotency Behavior
- Existing titles matching by ISBN (including hyphen-agnostic matching) or matching normalized title and author are enriched with missing metadata fields without overwriting administrator edits or resetting circulation metrics.
- Available copies on existing circulating books are strictly preserved.
- Running the command consecutively produces 0 duplicate records:

```text
First Run:
 - Categories created: 6
 - Books created: 83
 - Books updated: 7
 - Cover assets linked: 46
 - Total books: 90

Second Run:
 - Categories created: 0
 - Books created: 0
 - Books updated: 0
 - Books skipped (unchanged): 90
 - Total books: 90
```

---

## 6. Interface and Discovery Capabilities

- **Catalogue Index (`/books/`)**:
  - Grid presentation showing cover thumbnails, author, publication year, publisher, Dewey placement, and stock availability.
  - Sorting support: by Title (A-Z), Author (A-Z), Publication Year (Newest first), or Recently Added.
  - Pagination: 15 volumes per folio page with accessible navigation controls.
  - Search: Full-text matching across title, author, and ISBN.
  - Filter: Academic discipline selector and availability toggle (In Stock vs In Circulation).

- **Monograph Dossier (`/books/<id>/`)**:
  - Archival masthead displaying high-resolution cover thumbnail and accession status.
  - Bibliographic dossier table detailing Academic Discipline, Publisher, Publication Year, Edition, Language, Page Count, Institutional Valuation, and Shelf Location.
  - Reader requisition interface and staff circulation history.
