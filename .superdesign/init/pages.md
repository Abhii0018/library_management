# Page Dependency Trees

## `/` Home / Public catalog

- `templates/landing.html`
  - `static/css/styles.css`
  - `static/js/main.js`
  - `static/images/library-logo.svg`
  - `static/images/library_atrium_bg.jpg`

## Authenticated dashboard

- `templates/dashboard/member_dashboard.html`
  - `templates/base.html`
    - `templates/includes/sidebar.html`
    - `templates/includes/messages.html`
  - `static/css/styles.css`
  - `static/js/main.js`

## Librarian dashboard

- `templates/dashboard/librarian_dashboard.html`
  - `templates/base.html`
    - `templates/includes/sidebar.html`
    - `templates/includes/messages.html`
  - `static/css/styles.css`
  - `static/js/main.js`
