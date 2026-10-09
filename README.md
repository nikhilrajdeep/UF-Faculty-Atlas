# UF Faculty Atlas

Search University of Florida faculty by college, department, research interests, teaching, Google Scholar and current students. Independent project built from public UF web pages — **not an official UF product**.

## How it works

```
GitHub Actions (refresh.yml)                          GitHub Pages (docs/ on main)
  reads gradcatalog.ufl.edu  ─►  colleges + departments     docs/index.html + assets   (the app)
  opens each department site ─►  faculty list, students     docs/data/*.json            (the database)
  opens each faculty profile ─►  email, research, teaching,
                                 Scholar, extension, lab
  commits docs/data/*.json   ────────────────────────────►  app loads these files directly
  publishes live progress    ─►  branch `refresh-status`  ─►  progress bar in the app
```

* **The database is in this repository**: `docs/data/faculty.json`, `students.json`, `coverage.json`, `meta.json`. The app reads those files; nothing else.
* **Coverage is reported honestly**: the *Data coverage* tab lists every department and whether its faculty list was found. Departments whose site layout isn't recognised fall back to the graduate catalog roster (name, rank, department).
* Student **e-mails and home locations are not collected**; only name, program and advisor as published by the department.

## GitHub Pages: "Deploy from a branch" (no Actions deploy)

Settings → Pages → Build and deployment → **Source: Deploy from a branch** → Branch **main**, folder **/docs** → Save.

*What the two options mean:* "GitHub Actions" runs a custom workflow that builds and publishes the site. "Deploy from a branch" simply serves the files already committed in a folder — simpler, and it is what this project uses. The built app is committed in `docs/`, so no deploy workflow exists.

The crawler (`refresh.yml`) still runs on GitHub Actions because UF's sites can only be read from a server; it only *collects data* and commits it. After it commits, GitHub Pages republishes by itself.

## Refreshing from the web app (no GitHub visit)

GitHub Pages is static, so a button on the page can't start a GitHub job by itself, and a token can't be put in the page. A tiny free relay (Cloudflare Worker, `worker/relay.js`) keeps the token private and offers two safe endpoints: `GET /status` and `POST /refresh` (refuses while a refresh is running or if data was refreshed in the last 3 hours).

One-time setup (about 10 minutes):

1. GitHub → Settings → Developer settings → **Fine-grained personal access token**, only for this repository: *Actions: Read and write*, *Contents: Read*. Copy it.
2. `cd worker && npx wrangler deploy` (free Cloudflare account), then `npx wrangler secret put GITHUB_TOKEN` and paste the token.
3. Put the Worker's address in `public/config.json` → `"refreshApi": "https://uf-faculty-atlas-relay.<you>.workers.dev"`, run `npm run build`, commit `docs/`.

After that, **Database updates → Refresh database now** starts the crawl and shows a progress bar. The percentage is real work done (departments read, then profile pages read, out of a count known once the department lists are in), with an ETA that sharpens as it goes. When it finishes, the page waits for GitHub Pages to publish and reloads the data itself.

Without the relay the page still shows the progress of any running refresh, but can't start one.

## Everyday commands

```bash
npm install
npm run dev        # local app, reads docs/data
npm run build      # builds the app into docs/ (commit the result); docs/data is left untouched
python -m pip install -r requirements.txt pytest
python -m pytest tests -q
PYTHONPATH=scripts ATLAS_ONLY="soil" ATLAS_OUT=data/dev-run python -m atlas.crawl   # test crawl of matching departments
```

Start a refresh by hand: Actions → *Refresh UF faculty database* → Run workflow (optionally enter department words to test on a few departments).

## Files

| Path | Purpose |
|---|---|
| `src/` | React app (faculty, students, coverage, updates) |
| `docs/` | Built app + database served by GitHub Pages |
| `scripts/atlas/` | Crawler: `crawl.py` (pipeline), `parsers.py` (HTML parsing), `fetch.py` (polite fetching, robots.txt), `publish.py` (live progress) |
| `scripts/validate.py` | Refuses to commit a bad run |
| `worker/` | Optional refresh relay for the in-app button |
| `tests/` | Parser and pipeline tests, including regressions from real UF pages |

## Notes on responsible scraping

The crawler identifies itself, honours `robots.txt` and crawl delays, waits at least one second between requests to the same host, and only reads pages on `*.ufl.edu`. If UF's rules change, adjust `scripts/atlas/fetch.py`.
