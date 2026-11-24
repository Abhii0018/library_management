# LibriCore - Professional Library Management System

A robust, full-featured Library Management System built with Python and Django. Designed following clean architecture principles, role-based authorization, server-side business integrity, and an intuitive UI.

---

## 🚀 Key Features

### 1. Authentication & Role-Based Access Control
- Custom User model (`accounts.User`) extending `AbstractUser` with explicit role segregation (`LIBRARIAN` vs `MEMBER`).
- Dedicated `MemberProfile` tracking membership numbers (e.g., `MEM-10023`), phone numbers, addresses, borrowing quotas, and account status.
- Strict authorization via custom `@librarian_required` view decorators.
- Built-in user self-service: registration, profile update, and password changes.

### 2. Librarian / Admin Management
- **Dashboard:** Live analytics including Total Titles, Available Copies on shelves, Issued Copies, Total Members, Overdue Loans, and Pending Fines.
- **Books Management:** Complete CRUD operations, real-time availability tracking (`total_copies` vs `available_copies`), multi-attribute search (title, author, ISBN), category filtering, and shelf location mapping.
- **Member Directory:** Member registration, detail view with active loans & history, edit quotas, and instant 1-click block/unblock toggles.
- **Circulation (Issue Book):** Multi-rule validation (checks book availability, borrower block status, max active loans quota, and duplicate borrow prevention). Automatically decrements available copies within atomic transactions.
- **Circulation (Return Book):** Real-time overdue calculation and automatic fine generation based on configurable daily rates. Automatically restores shelf copies.
- **Transactions Audit:** Searchable and filterable master register (`Issued`, `Returned`, `Overdue`).
- **Fine Management:** Fine ledger with overdue day breakdown, pending vs. paid counters, and collection/settlement actions.

### 3. Member / Student Portal
- **Member Dashboard:** Overview of personal loans, return dates, countdown to due dates, overdue alert badges, and pending fines.
- **Catalog Browsing:** Search books by title, author, or category with real-time stock availability.
- **Loan History:** Full chronological record of past borrowed and returned books.

---

## 🛠️ Tech Stack
- **Backend:** Python 3, Django 6
- **Database:** SQLite (Relational ORM with transaction atomicity)
- **Frontend:** Django Templates, Semantic HTML5, Custom Responsive CSS (No bulky external UI frameworks required)
- **Authentication:** Django Built-in Auth with PBKDF2 password hashing

---

## Demo Data

No accounts or passwords are committed to the repository. After migrating and loading the catalogue, create demo data explicitly:

```bash
uv run python manage.py setup_admin --username <admin> --password <password>
uv run python manage.py seed_catalog
uv run python manage.py seed_demo --password <demo-password>
```

If `--password` and the `DEMO_PASSWORD` environment variable are both omitted, a random password is generated and printed once.

`seed_demo` creates `demo_librarian` (staff), `demo_member1`-`demo_member3` and `demo_blocked`, plus 3 pending requests, 3 active loans (one overdue), and 3 completed returns with fee records. It is idempotent, never changes existing passwords or records, and keeps book inventory consistent with active loans.

---

## Setup and Running Instructions

### Option A: Using uv (Recommended)

1. Sync dependencies:
```bash
uv sync
```

2. Run database migrations:
```bash
uv run python manage.py migrate
```

3. Populate curated library catalogue (90 verified titles across 10 disciplines):
```bash
uv run python manage.py seed_catalog
```
Use `--dry-run` to preview changes without modifying the database:
```bash
uv run python manage.py seed_catalog --dry-run
```

4. (Optional) Create demo accounts and circulation data (see Demo Data above), then run the development server:
```bash
uv run python manage.py runserver
```

Open your browser at `http://127.0.0.1:8000/`.

---

### Option B: Traditional Python venv

1. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run migrations, seed data, and run server:
```bash
python manage.py migrate
python manage.py seed_catalog
python manage.py seed_demo --password <demo-password>
python manage.py runserver
```

---

## Running Automated Tests

Run the test suite with uv:

```bash
uv run python manage.py test
```

Or using standard python inside an activated virtual environment:

```bash
python manage.py test
```
