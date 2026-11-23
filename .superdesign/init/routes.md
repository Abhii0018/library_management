# Routes

The project uses Django URL configurations.

## Public home

- URL: `/`
- View: `dashboard.views.index`
- Template: `templates/landing.html`
- Layout: public landing layout

## Authenticated dashboards

- URL: dashboard routes configured in `dashboard/urls.py`
- Templates: `templates/dashboard/member_dashboard.html`, `templates/dashboard/librarian_dashboard.html`
- Layout: `templates/base.html` and `templates/includes/sidebar.html`

## Catalog

- URL: books routes configured in `books/urls.py`
- Templates: `templates/books/book_list.html`, `templates/books/book_detail.html`
- Layout: `templates/base.html`
