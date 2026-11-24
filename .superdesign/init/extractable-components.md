# Extractable Components

## AppShell

- Source: `templates/base.html`
- Category: layout
- Description: Authenticated sidebar/topbar/content shell.
- Extractable props: page title, subtitle, page actions, active navigation state
- Hardcoded: LibriCore branding, shell spacing, sidebar structure

## Sidebar

- Source: `templates/includes/sidebar.html`
- Category: layout
- Description: Role-aware navigation and account footer.
- Extractable props: role, active item, user identity
- Hardcoded: navigation labels, inline SVG icons, logo

## LandingHero

- Source: `templates/landing.html`
- Category: layout
- Description: Public hero with search, category links, and animated book visual.
- Extractable props: search URL, categories, authentication actions
- Hardcoded: brand copy, book illustration, hero composition
