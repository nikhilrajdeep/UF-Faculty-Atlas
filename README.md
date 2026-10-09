# UF Faculty Atlas

A responsive React + Vite interface for exploring UF graduate faculty, filtering by department, college, research specialty, and exporting CSV. This is an independent project, **not an official UF product**.

## Project structure

- `src/main.jsx` – faculty search, filters, profiles, updates progress and CSV.
- `src/style.css` – responsive design.
- `public/data/faculty.json` – catalog database, initially empty until refreshed.
- `public/data/config.json` – target GitHub repository.
- `scripts/refresh.py` – official catalog scraper with minimum-record guard.
- `.github/workflows/refresh.yml` – manual and scheduled catalog refresh.
- `.github/workflows/deploy.yml` – build and deploy to GitHub Pages.

## Setup

1. On GitHub, open **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. Open **Actions → Refresh UF faculty database → Run workflow**. Check the logs for actual scraper success; scraper changes may be needed if UF updates its pages.
3. Open **Actions → Deploy faculty app to GitHub Pages**, or push any change to main.
4. View: https://nikhilrajdeep.github.io/UF-Faculty-Atlas/

## Local development

```bash
npm install
npm run dev
```

Refresh the dataset locally:

```bash
python -m pip install -r requirements.txt
python scripts/refresh.py
```

## Current limitations

The current importer is a first-pass extraction from UF's graduate faculty catalog and requires validation. College mapping and supplemental research, lab, course, student, email and Scholar information are **not** automatically enriched in this release. Fields remain blank rather than guessing. Only faculty identified as part of the graduate catalog are covered, not all UF employees. Scraping should respect UF's published access rules and rate limits.

The public app **cannot securely trigger GitHub Actions**; use the GitHub workflow page to launch an update. The in-app progress meter polls the public GitHub Actions API for step-level completion. A completed failed run reaches 100% but is shown as failed.

## Accuracy

Cross-check imported names, titles and departments against official UF pages before relying on the database. Do not publish inferred student affiliations, guessed email addresses or guessed scholar profiles.
