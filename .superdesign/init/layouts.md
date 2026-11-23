# Shared Layouts

## Public landing layout

- Source: `templates/landing.html`
- Description: Full-width public library marketing/catalog page with sticky navigation, hero, stats, featured books, workflow, policies, CTA, and footer.

## Authenticated app shell

- Source: `templates/base.html`
- Description: Fixed sidebar plus topbar and content area.

```django
{% load static %}
<div class="app-container">
  {% include 'includes/sidebar.html' %}
  <main class="app-main">
    <header class="app-topbar">...</header>
    <div class="content-body">{% block content %}{% endblock %}</div>
  </main>
</div>
```

## Sidebar

- Source: `templates/includes/sidebar.html`
- Description: Role-aware navigation for administrators, staff, and members with branded logo and account footer.
