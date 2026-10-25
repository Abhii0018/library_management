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

## 📋 Default Credentials (Seeded)

The database comes pre-seeded with sample books, members, categories, active loans, and overdue fines:

| Role | Username | Password | Notes |
| :--- | :--- | :--- | :--- |
| **Librarian / Admin** | `librarian` | `admin123` | Full access to management & circulation |
| **Member (Active)** | `rahul` | `member123` | Active loans and pending fine demo |
| **Member (Overdue)** | `priya` | `member123` | Has an active overdue loan |
| **Member (Good standing)**| `arjun` | `member123` | Clean borrowing history |
| **Member (Blocked)** | `sneha` | `member123` | Blocked member (cannot borrow books) |

---

## ⚙️ Setup & Running Instructions

### 1. Activate Virtual Environment
```bash
source venv/bin/activate
```

### 2. Run Database Migrations
```bash
python manage.py migrate
```

### 3. (Optional) Re-seed Demo Data
```bash
python manage.py seed_library
```

### 4. Run the Development Server
```bash
python manage.py runserver
```

Open your browser at `http://127.0.0.1:8000/`.

---

## 🧪 Running Automated Tests

Run the test suite covering authentication, role decorators, copy concurrency, issue validations, return calculations, and fine generation:

```bash
python manage.py test
```
