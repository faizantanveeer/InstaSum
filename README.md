<div align="center">

# Insta Sum

### `Any account.` &nbsp;&nbsp; `Every reel.` &nbsp;&nbsp; `Instant insight.`

<br />

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0.2-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![React](https://img.shields.io/badge/React-18.3.1-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-5.4.10-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![Cloudinary](https://img.shields.io/badge/Cloudinary-Media-3448C5?style=for-the-badge&logo=cloudinary&logoColor=white)](https://cloudinary.com)
[![License](https://img.shields.io/badge/License-MIT-111111?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-1DB954?style=for-the-badge)]()

<br />

> Insta Sum turns any public Instagram profile into something you can **search, scan, and export**
> instead of manually watching reel after reel. Search a profile, pull the reel catalog, transcribe
> audio locally with Whisper, and generate titles and summaries with OpenAI or Azure OpenAI —
> backed by Supabase PostgreSQL, Cloudinary media storage, and a React SPA that stays live while jobs run.

<br />

[**Quick Start**](#9-installation-and-setup) &nbsp;·&nbsp;
[**Architecture**](#4-system-architecture-diagram) &nbsp;·&nbsp;
[**Stack**](#6-tech-stack) &nbsp;·&nbsp;
[**Configuration**](#10-environment-variables) &nbsp;·&nbsp;
[**Troubleshooting**](#19-troubleshooting)

<br />

</div>

---

## 2. Table of Contents

<table>
<tr>
<td valign="top" width="33%">

**Getting Started**
- [03 · Features](#3-features)
- [04 · Architecture](#4-system-architecture-diagram)
- [05 · Pipeline](#5-processing-pipeline-flowchart)
- [06 · Tech Stack](#6-tech-stack)
- [07 · Project Structure](#7-project-structure)
- [08 · Prerequisites](#8-prerequisites)
- [09 · Installation](#9-installation-and-setup)

</td>
<td valign="top" width="33%">

**Configuration**
- [10 · Environment Variables](#10-environment-variables)
- [11 · Supabase Setup](#11-supabase-setup)
- [12 · Cloudinary Setup](#12-cloudinary-setup)
- [13 · Instagram Fetch Layers](#13-instagram-fetch-layer-setup)
- [14 · Frontend Development](#14-frontend-development)

</td>
<td valign="top" width="33%">

**Reference**
- [15 · How It Works](#15-how-it-works---plain-english)
- [16 · API Endpoints](#16-api-endpoints-reference)
- [17 · Whisper Models](#17-whisper-model-selection-guide)
- [18 · Known Limitations](#18-known-limitations)
- [19 · Troubleshooting](#19-troubleshooting)
- [20 · Contributing](#20-contributing)
- [21 · Roadmap](#21-roadmap)
- [22 · License](#22-license)
- [23 · Acknowledgements](#23-acknowledgements)

</td>
</tr>
</table>

---

## 3. Features

<table>
<tr>
<th align="left" width="50%">⚙️ &nbsp; Backend & Data</th>
<th align="left" width="50%">🖥️ &nbsp; Frontend & UX</th>
</tr>
<tr>
<td valign="top">

- **3-layer Instagram fetch** — Apify → Instaloader → yt-dlp browser-cookie fallback
- **Global fetch lock** to avoid concurrent Instagram scraping from multiple users
- **Metadata caching** by profile with a configurable freshness window
- **Supabase PostgreSQL** via SQLAlchemy, with generated TSVECTOR search and GIN index
- **User-scoped data** — profiles, reels, jobs, and error rows in the database
- **Cloudinary storage** for reel audio and thumbnail assets
- **Local Whisper transcription** with configurable model size
- **AI title and summary** generation through OpenAI or Azure OpenAI
- **Offline summary fallback** through Sumy plus heuristic title fallback
- **Background worker threads** for per-reel and batch generation jobs
- **JSON and CSV export** for any analyzed profile
- **Email/password authentication** with Flask sessions and hashed passwords

</td>
<td valign="top">

- **React SPA** built with Vite and served by Flask from a single static bundle
- **React Router** navigation with no page reloads across login, home, and profile views
- **Dual light and dark monochrome themes** with persistent user preference
- **Sidebar** with search, recent-profile history, collapse control, and app shell layout
- **Home screen** with recent profiles and focused search CTA
- **Reel grid and list layouts** with keyword filtering, status filtering, and sorting
- **12-item pagination** by default, driven from backend config
- **Detail modal** with summary, transcript, metadata, and audio playback
- **Live client polling** for reel and batch job status without relying on SSE in the UI
- **Toast notification system** for auth, fetch, generation, and export feedback
- **Monochrome logo system** and responsive layout from mobile to desktop
- **Google sign-in button** fully designed in the UI, but not yet wired to a provider

</td>
</tr>
</table>

---

## 4. System Architecture Diagram

```
+------------------------------------------------------------------------------------------------------------------+
|                                                USER BROWSER                                                      |
|  React SPA served from /app/static/dist                                                                          |
|  Routes: /login, /signup, /dashboard, /profile/:username                                                         |
|  UI: home screen, sidebar history, reel grid, filters, modal, toasts, theme toggle                              |
|  Live updates: polling /api/reels/:id/status and /api/jobs/:id/status                                            |
+-----------------------------------------------------------+------------------------------------------------------+
                                                            |
                                                            | same-origin fetch() + session cookie
                                                            v
+------------------------------------------------------------------------------------------------------------------+
|                                               FLASK APPLICATION                                                  |
|                                                                                                                  |
|  Main routes                                      JSON API routes                                                |
|  - SPA entry and catch-all                        - /api/auth/*                                                  |
|  - /dashboard/search, /analyze, /results/:u       - /api/config                                                  |
|                                                   - /api/profiles, /api/profiles/search                          |
|  Background execution                             - /api/profiles/:username                                      |
|  - worker threads started from API routes         - /api/reels/:id/status, /api/reels/:id/generate              |
|  - SSE compat: /api/stream/:job_id                - /api/jobs/:id/status, /api/profiles/:id/generate-all        |
|                                                   - /export/profile/:id, /proxy-image                            |
+-----------------------------+--------------------------------------+---------------------------+------------------+
                              |                                      |                           |
                              v                                      v                           v
+-----------------------------+------------------+   +--------------+----------------+   +-------+------------------+
|      Instagram fetch service                   |   |    Processing services         |   |     Persistence         |
|  app/services/instagram.py                     |   |  media.py                      |   |  Supabase PostgreSQL    |
|                                                |   |  transcription.py              |   |  via SQLAlchemy         |
|  1. Apify actor: apify/instagram-scraper       |   |  summarization.py              |   |                         |
|  2. Instaloader with saved .session file       |   |                                |   |  Tables: users,         |
|  3. yt-dlp browser-cookie fallback             |   |  reel URL -> temp audio/thumb  |   |  profiles, reels,       |
|                                                |   |  -> Whisper -> OpenAI/Azure    |   |  jobs, reel_errors      |
|  Output: normalized reel metadata              |   |  -> Sumy fallback if needed    |   |                         |
|  + profile metadata                            |   |  -> Cloudinary upload          |   |  Search: TSVECTOR +     |
|                                                |   |                                |   |  GIN index              |
+-----------------------------+------------------+   +--------------+----------------+   +-------------------------+
                              |                                      |                           |
                              v                                      v                           |
               +--------------+-----------+            +------------+------------+              |
               |  Apify API               |            |  Cloudinary              |<------------+
               |  Production fetch layer  |            |  insta_sum/<username>/   |
               +--------------------------+            |  audio/ and thumbnails/  |
                                                       +--------------------------+
```

---

## 5. Processing Pipeline Flowchart

```
[User clicks "Generate" or "Generate all"]
                |
                v
[POST /api/reels/:id/generate  or  /api/profiles/:id/generate-all]
                |
                v
[Create Job row and start worker thread]
                |
                v
      +---------+----------------------------+
      |  Reel already processed?             |
      |  regenerate = false?                 |
      +-------+------------------------------+
          yes |                     | no
              v                     v
  [Mark skipped, update job]  [Mark reel as processing]
              |                     |
              +----------+----------+
                         |
                         v
             [Open temp media workspace]
                         |
                         v
             [yt-dlp download for this reel URL]
                         |
                         v
         +---------------+------------------+
         | Audio path exists and valid?     |
         +-------+--------------------------+
              no |                  | yes
                 v                  v
    [Fail reel: MediaError]  [Run local Whisper transcription]
                                    |
                         +----------+----------+
                         | Transcript has       |
                         | speech content?      |
                         +----+----------+------+
                           no |          | yes
                              v          v
               [Store: "No spoken   [Store transcript]
                content detected."]      |
                              |          |
                              +----+-----+
                                   |
                                   v
                     [Generate title + detailed summary]
                                   |
                      +------------+-------------+
                      | Azure OpenAI configured  |
                      | and responds?            |
                      +----+---------------------+
                        yes|              | no
                           v              v
                  [Use Azure]    +--------+---------+
                                 | OpenAI configured|
                                 | and responds?    |
                                 +----+-------------+
                                   yes|        | no
                                      v        v
                             [Use OpenAI] [Use Sumy /
                                          heuristic fallback]
                                      |        |
                                      +---+----+
                                          |
                                          v
                              [Upload audio to Cloudinary]
                                          |
                                          v
                              [Upload thumbnail to Cloudinary]
                                          |
                               +----------+----------+
                               | Audio upload OK?    |
                               +----+----------------+
                                 no |          | yes
                                    v          v
                        [Fail reel +  [Write reel fields to Postgres]
                         persist error]          |
                                                 v
                                    [Update job counters and status]
                                                 |
                                                 v
                     [React polls /api/reels/:id/status and /api/jobs/:id/status]
                                                 |
                                                 v
                                  [Card updates in place in the browser]
```

---

## 6. Tech Stack

| Layer | Technology | Version | Role | Notes |
| --- | --- | --- | --- | --- |
| Frontend | React | 18.3.1 | SPA UI | Route-based client rendering |
| Frontend | React Router DOM | 6.30.1 | Client-side routing | `/dashboard`, `/profile/:username`, auth pages |
| Frontend | Lucide React | 0.468.0 | Icon system | Single icon library across the app |
| Frontend | CSS custom properties | latest | Design system | Dual light/dark monochrome theme |
| Build tools | Vite | 5.4.10 | SPA build and dev server | Outputs to `app/static/dist` |
| Build tools | `@vitejs/plugin-react` | 4.3.4 | JSX transform | Vite React integration |
| Backend framework | Flask | 3.0.2 | HTTP server and route handling | Serves SPA and JSON APIs |
| Backend framework | Werkzeug security | latest | Password hashing | Email/password auth |
| Backend framework | Flask-Limiter | 3.5.0 | Optional request throttling | Disabled by default |
| Database | Supabase PostgreSQL | managed service | Primary relational database | Accessed through `DATABASE_URL` |
| ORM | SQLAlchemy | >= 2.0.30 | Models, sessions, schema | Uses PostgreSQL features |
| Search | PostgreSQL TSVECTOR + GIN | built-in | Full-text search index | Generated `search_vector` on reels |
| Auth | Flask sessions | built-in | Session management | Stores `user_id` in secure cookie-backed session |
| Media storage | Cloudinary Python SDK | 1.41.0 | Audio and thumbnail storage | Public HTTPS delivery URLs |
| Instagram fetching | Apify client | >= 1.6.0 | Primary production fetcher | Actor: `apify/instagram-scraper` |
| Instagram fetching | Instaloader | >= 4.10.2 | Secondary authenticated fetcher | Reuses saved `.session` file |
| Instagram fetching | yt-dlp | 2025.1.15 | Local-dev metadata fallback | Browser-cookie fallback only |
| Media download | yt-dlp | 2025.1.15 | Reel media extraction | Used per reel for audio/temp media |
| Audio processing | FFmpeg / ffprobe | system install | Audio extraction and conversion | Mandatory for the processing pipeline |
| Transcription | openai-whisper | latest | Local speech-to-text | Runs on local CPU/GPU |
| AI summarization | OpenAI Python SDK | 1.12.0 | Title and summary generation | Standard OpenAI path |
| AI summarization | Azure OpenAI | via `openai` SDK | Azure fallback/primary | Uses deployment-based chat completions |
| Fallback summarization | Sumy | 0.11.0 | Offline summary fallback | LSA summarizer |
| NLP support | NLTK | 3.8.1 | Tokenization support | Used by Sumy pipeline |
| HTTP clients | requests | 2.31.0 | Direct OpenAI HTTP fallback | Also general API calls |
| HTTP clients | httpx | 0.26.0 | SDK transport dependency | Used by OpenAI ecosystem |
| Real-time updates | Client polling | latest | Reel/job updates | Current SPA path polls every 3 seconds |
| Real-time updates | Server-Sent Events | built-in | Compatibility stream | `/api/stream/:job_id` remains available |
| Config | python-dotenv | 1.0.1 | `.env` loading | App boot and setup scripts |
| Database driver | psycopg2-binary | 2.9.10 | PostgreSQL connectivity | Required for SQLAlchemy engine |

---

## 7. Project Structure

```
Insta Sum/
|-- .env.example                       # Sample environment file for local setup
|-- .gitignore                         # Ignores secrets, sessions, temp files, build outputs
|-- README.md                          # Project documentation
|-- requirements.txt                   # Python dependencies
|-- run.py                             # Flask development entry point
|
|-- scripts/
|   `-- init_supabase_schema.py        # Drops and recreates the main Postgres schema
|
|-- docs/
|   |-- architectural_diagram.png      # Exported architecture image
|   `-- processing_pipeline.png        # Exported processing-flow image
|
|-- app/
|   |-- __init__.py                    # Flask app factory and blueprint registration
|   |-- config.py                      # Environment-backed config object
|   |-- db.py                          # SQLAlchemy engine/session setup
|   |-- extensions.py                  # Flask-Limiter instance
|   |-- models.py                      # User, Profile, Reel, Job, ReelError models
|   |
|   |-- routes/
|   |   |-- __init__.py                # Route package marker
|   |   |-- api.py                     # JSON APIs, exports, job polling, proxy image
|   |   |-- auth.py                    # Legacy server-handled auth routes
|   |   `-- main.py                    # SPA entry, compatibility search routes, catch-all
|   |
|   |-- services/
|   |   |-- __init__.py                # Service package marker
|   |   |-- auth.py                    # Session helpers and auth guard
|   |   |-- captcha.py                 # Optional captcha support
|   |   |-- instagram.py               # 3-layer profile fetch service
|   |   |-- jobs.py                    # Worker-event helpers and background queue support
|   |   |-- media.py                   # yt-dlp temp download and Cloudinary upload pipeline
|   |   |-- storage.py                 # Cloudinary upload/delete helpers
|   |   |-- summarization.py           # OpenAI, Azure OpenAI, and Sumy summarization
|   |   |-- transcription.py           # Local Whisper loading and transcription
|   |   `-- utils.py                   # Shared service utilities
|   |
|   `-- static/
|       |-- app.js                     # Legacy static asset retained from earlier UI
|       |-- styles.css                 # Legacy static stylesheet retained from earlier UI
|       `-- dist/
|           |-- index.html             # Built React SPA entry served by Flask
|           `-- assets/                # Generated Vite JS/CSS chunks
|
|-- frontend/
|   |-- index.html                     # Vite HTML template
|   |-- package.json                   # Frontend scripts and npm dependencies
|   |-- package-lock.json              # Locked frontend dependency tree
|   |-- vite.config.js                 # Vite build output and Flask proxy config
|   `-- src/
|       |-- App.jsx                    # React Router setup and protected routes
|       |-- copy.js                    # Centralized user-facing copy strings
|       |-- main.jsx                   # SPA bootstrap and providers
|       |-- styles.css                 # Global tokens, layout, theme, and component styles
|       |
|       |-- components/
|       |   |-- AppShell.jsx           # Sidebar + top-right actions shell
|       |   |-- AuthLayout.jsx         # Login/signup split-layout wrapper
|       |   |-- BrandLogo.jsx          # Monochrome app mark and logotype
|       |   |-- GridToolbar.jsx        # Sort, filter, view mode, keyword search
|       |   |-- PaginationBar.jsx      # Paged reel navigation
|       |   |-- ProfileHeader.jsx      # Profile hero, refresh, export, generate-all controls
|       |   |-- ProfileSearchForm.jsx  # Shared search input with stable loader
|       |   |-- ReelCard.jsx           # Grid/list card for each reel
|       |   |-- ReelDetailModal.jsx    # Summary/transcript modal with navigation
|       |   |-- Sidebar.jsx            # Search, history, collapse, session footer
|       |   |-- States.jsx             # Empty, error, private, and loading states
|       |   `-- ThemeToggleButton.jsx  # Theme switcher
|       |
|       |-- contexts/
|       |   |-- AuthContext.jsx        # Auth session bootstrap and state
|       |   |-- ThemeContext.jsx       # Light/dark theme persistence
|       |   |-- ToastContext.jsx       # Toast notification system
|       |   `-- WorkspaceContext.jsx   # Shared profile search/history state
|       |
|       |-- hooks/
|       |   |-- useApi.js              # Thin fetch wrapper hook
|       |   `-- useWorkspace.js        # Workspace context hook
|       |
|       |-- lib/
|       |   |-- api.js                 # Low-level API request helper
|       |   |-- format.js              # Number/date formatting helpers
|       |   |-- media.js               # Thumbnail/audio URL resolution helpers
|       |   `-- profile.js             # Profile normalization helpers
|       |
|       `-- pages/
|           |-- DashboardPage.jsx      # Home screen and recent profiles
|           |-- LoginPage.jsx          # Login form route
|           |-- ProfilePage.jsx        # Reel workspace route
|           `-- SignupPage.jsx         # Signup form route
|
`-- tmp/                               # Temporary workspace used during media processing
```

---

## 8. Prerequisites

> ⚠️ **FFmpeg is mandatory.** Reel download, MP3 extraction, and Whisper preprocessing will fail without `ffmpeg` and `ffprobe` on the machine.

| Dependency | Minimum | Windows (winget) | macOS (Homebrew) | Ubuntu / Debian (apt) |
| --- | --- | --- | --- | --- |
| Python | 3.9+ | `winget install Python.Python.3.11` | `brew install python@3.11` | `sudo apt-get install -y python3 python3-venv python3-pip` |
| Node.js | 18+ | `winget install OpenJS.NodeJS.LTS` | `brew install node` | `sudo apt-get install -y nodejs npm` |
| npm | 9+ | bundled with Node.js | bundled with Node.js | bundled with Node.js |
| Git | latest | `winget install Git.Git` | `brew install git` | `sudo apt-get install -y git` |
| FFmpeg | latest stable | `winget install Gyan.FFmpeg` | `brew install ffmpeg` | `sudo apt-get install -y ffmpeg` |

---

## 9. Installation and Setup

### 1 · Clone

```bash
git clone https://github.com/faizantanveeer/InstaSum.git
cd InstaSum
```

### 2 · Python virtual environment

```bash
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3 · Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4 · Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 5 · Copy the sample environment file and fill in your values

```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

### 6 · Configure at least one fetch layer and one summary path

**Production minimum:**
```
DATABASE_URL
CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
APIFY_TOKEN
OPENAI_API_KEY  (or Azure OpenAI settings)
```

**Practical local fallback:**
```
IG_USERNAME, IG_PASSWORD  (for Instaloader)
IG_BROWSER                (optional browser-cookie fallback)
```

> 💡 If you do not set OpenAI or Azure OpenAI keys, the app still falls back to heuristic title generation and Sumy-based summary generation, but results will be weaker.

### 7 · Set up Instagram auth artifacts

- For Instaloader: set `IG_USERNAME` and `IG_PASSWORD` to a burner Instagram account.
- For yt-dlp media downloads: place a Netscape-format cookies file at the path in `IG_COOKIES_FILE`.
- For local-dev browser-cookie fallback: set `IG_COOKIES_FROM_BROWSER=1` and `IG_BROWSER=edge,chrome`.

### 8 · Initialize the Supabase schema

```bash
# Safe first boot
python -c "from app import create_app; create_app(); print('Database initialized')"

# Full reset — drops and recreates all app tables
python scripts/init_supabase_schema.py
```

### 9 · Build the React frontend

```bash
npm --prefix frontend run build
```

### 10 · Run Flask

```bash
python run.py
```

### 11 · Frontend development mode (second terminal)

```bash
cd frontend
npm run dev
```

| Mode | URL |
| --- | --- |
| Flask (production build) | `http://127.0.0.1:5000` |
| Vite dev server | `http://127.0.0.1:5173` |

> 💡 In dev mode, Vite proxies `/api`, `/auth`, `/dashboard`, `/export`, `/thumbnails`, `/audio`, and `/proxy-image` back to Flask on port `5000`, so session cookies and API calls stay same-origin.

---

## 10. Environment Variables

### Flask and App

| Variable | Required | Default | Description | Where to get it |
| --- | --- | --- | --- | --- |
| `SECRET_KEY` | Yes | `dev-secret` | Flask session signing key | Generate your own random secret |
| `FLASK_ENV` | No | `development` | Runtime mode | Set manually |
| `DATABASE_URL` | Yes | none | SQLAlchemy connection string for Supabase PostgreSQL | Supabase project settings |
| `SESSION_COOKIE_SAMESITE` | No | `Lax` | Session cookie same-site policy | Set manually |
| `SESSION_COOKIE_SECURE` | No | `0` | Set to `1` behind HTTPS | Set manually |
| `TEMP_DIR` | No | `./tmp` | Temporary working directory for media download/transcription | Set manually |
| `CACHE_TTL_HOURS` | No | `24` | Generic cache TTL used by the app | Set manually |
| `PAGE_SIZE` | No | `12` | Default page size returned by `/api/config` | Set manually |
| `MAX_REELS` | No | `100` | Max reels requested per profile fetch | Set manually |
| `MAX_REEL_SECONDS` | No | `180` | Upper-bound guard for reel duration | Set manually |

### Supabase

| Variable | Required | Default | Description | Where to get it |
| --- | --- | --- | --- | --- |
| `DATABASE_URL` | Yes | none | Primary database connection used by the app | Supabase database settings |
| `SUPABASE_URL` | No | blank | Project URL, kept in config for cloud integration | Supabase project settings |
| `SUPABASE_ANON_KEY` | No | blank | Public key, not required for current core runtime | Supabase project settings |
| `SUPABASE_SERVICE_ROLE_KEY` | No | blank | Service role key, not required for current core runtime | Supabase project settings |

### Cloudinary

| Variable | Required | Default | Description | Where to get it |
| --- | --- | --- | --- | --- |
| `CLOUDINARY_CLOUD_NAME` | Yes | blank | Cloudinary cloud name | Cloudinary dashboard |
| `CLOUDINARY_API_KEY` | Yes | blank | API key for media uploads | Cloudinary dashboard |
| `CLOUDINARY_API_SECRET` | Yes | blank | API secret for media uploads | Cloudinary dashboard |

### OpenAI

| Variable | Required | Default | Description | Where to get it |
| --- | --- | --- | --- | --- |
| `OPENAI_API_KEY` | No | blank | Standard OpenAI key for title and summary generation | OpenAI platform |
| `OPENAI_SUMMARY_MODEL` | No | `gpt-4o-mini` | Model used for titles and summaries | OpenAI platform |
| `OPENAI_WHISPER_MODEL` | No | `whisper-1` | Reserved config for hosted Whisper paths | OpenAI platform |

### Azure OpenAI

| Variable | Required | Default | Description | Where to get it |
| --- | --- | --- | --- | --- |
| `AZURE_OPENAI_ENDPOINT` | No | blank | Azure OpenAI endpoint | Azure portal |
| `AZURE_OPENAI_API_KEY` | No | blank | Azure OpenAI API key | Azure portal |
| `AZURE_OPENAI_API_VERSION` | No | `2024-12-01-preview` | API version passed to Azure client | Azure portal / docs |
| `AZURE_OPENAI_DEPLOYMENT` | No | blank | Deployment name used for chat completions | Azure portal |

### Instagram Fetching

| Variable | Required | Default | Description | Where to get it |
| --- | --- | --- | --- | --- |
| `APIFY_TOKEN` | Recommended | blank | Primary production fetch layer token | Apify console |
| `IG_USERNAME` | Recommended | blank | Burner Instagram username for Instaloader | Create a dedicated IG burner account |
| `IG_PASSWORD` | Recommended | blank | Burner Instagram password for Instaloader | Create a dedicated IG burner account |
| `IG_COOKIES_FILE` | No | `./instagram_cookies.txt` | Netscape-format cookies file used by yt-dlp media downloads | Export from your browser |
| `IG_COOKIES_FROM_BROWSER` | No | `0` | Enables browser-cookie fallback | Set manually |
| `IG_BROWSER` | No | `chrome` | Browser list for yt-dlp fallback, e.g. `edge,chrome` | Set manually |
| `IG_BROWSER_PROFILE` | No | blank | Optional browser profile name/path | Set manually |
| `FETCH_TIMEOUT_SECONDS` | No | `180` | Apify timeout budget | Set manually |
| `FETCH_DELAY_MIN` | No | `1.0` | Minimum polite delay for fallback fetchers | Set manually |
| `FETCH_DELAY_MAX` | No | `3.0` | Maximum polite delay for fallback fetchers | Set manually |
| `PROFILE_CACHE_MINUTES` | No | `60` | Metadata cache freshness window | Set manually |
| `FETCH_RETRY_MAX` | No | `3` | Reserved retry knob in config | Set manually |
| `FETCH_RETRY_BASE` | No | `1.5` | Reserved backoff knob in config | Set manually |

### Media Processing

| Variable | Required | Default | Description | Where to get it |
| --- | --- | --- | --- | --- |
| `WHISPER_MODEL` | No | `base` | Local Whisper model size | Set manually |
| `FFMPEG_LOCATION` | No | blank | Explicit path to ffmpeg/ffprobe if not on PATH | Local machine install |
| `DISABLE_LOCAL_WHISPER` | No | `0` | Dev-only switch to skip local Whisper loading | Set manually |

### Rate Limiting

| Variable | Required | Default | Description | Where to get it |
| --- | --- | --- | --- | --- |
| `RATELIMIT_ENABLED` | No | `0` | Enables Flask-Limiter | Set manually |
| `RATELIMIT_DEFAULT` | No | `200 per day` | Default Flask-Limiter rule | Set manually |

### Captcha

| Variable | Required | Default | Description | Where to get it |
| --- | --- | --- | --- | --- |
| `HCAPTCHA_SITEKEY` | No | blank | Optional hCaptcha site key | hCaptcha |
| `HCAPTCHA_SECRET` | No | blank | Optional hCaptcha secret | hCaptcha |
| `CAPTCHA_ENABLED` | No | `0` | Optional captcha switch | Set manually |

### Worker and Polling

| Variable | Required | Default | Description | Where to get it |
| --- | --- | --- | --- | --- |
| `WORKER_POLL_SECONDS` | No | `2` | Background worker heartbeat interval | Set manually |
| `STALE_JOB_MINUTES` | No | `30` | Reserved stale-job horizon | Set manually |
| `STATUS_POLL_SECONDS` | No | `2` | Exposed by `/api/config` | Set manually |
| `LIST_POLL_SECONDS` | No | `5` | Exposed by `/api/config` | Set manually |

### Export

| Variable | Required | Default | Description | Where to get it |
| --- | --- | --- | --- | --- |
| `EXPORT_MAX_ROWS` | No | `5000` | Caps rows included in exports | Set manually |

### Complete `.env.example`

```bash
# ── Flask and App ──────────────────────────────────────────────────────────────
SECRET_KEY=
FLASK_ENV=development
DATABASE_URL=
SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_SECURE=0

# ── OpenAI ─────────────────────────────────────────────────────────────────────
OPENAI_API_KEY=
OPENAI_SUMMARY_MODEL=gpt-4o-mini
OPENAI_WHISPER_MODEL=whisper-1

# ── Azure OpenAI ───────────────────────────────────────────────────────────────
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT=

# ── Local Transcription ────────────────────────────────────────────────────────
WHISPER_MODEL=base
FFMPEG_LOCATION=
DISABLE_LOCAL_WHISPER=0

# ── Supabase ───────────────────────────────────────────────────────────────────
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# ── Cloudinary ─────────────────────────────────────────────────────────────────
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=

# ── Instagram Fetching ─────────────────────────────────────────────────────────
APIFY_TOKEN=
# Use a dedicated burner account only. Never use your personal Instagram account.
IG_USERNAME=
IG_PASSWORD=
# Optional Netscape-format cookies file used by yt-dlp media downloads.
IG_COOKIES_FILE=./instagram_cookies.txt
IG_COOKIES_FROM_BROWSER=0
IG_BROWSER=edge,chrome
IG_BROWSER_PROFILE=
FETCH_TIMEOUT_SECONDS=180
FETCH_DELAY_MIN=1.0
FETCH_DELAY_MAX=3.0
PROFILE_CACHE_MINUTES=60
FETCH_RETRY_MAX=3
FETCH_RETRY_BASE=1.5

# ── Limits and UI Defaults ─────────────────────────────────────────────────────
MAX_REELS=100
PAGE_SIZE=12
MAX_REEL_SECONDS=180
CACHE_TTL_HOURS=24
TEMP_DIR=./tmp

# ── Worker and Polling ─────────────────────────────────────────────────────────
WORKER_POLL_SECONDS=2
STALE_JOB_MINUTES=30
STATUS_POLL_SECONDS=2
LIST_POLL_SECONDS=5

# ── Export ─────────────────────────────────────────────────────────────────────
EXPORT_MAX_ROWS=5000

# ── Optional Protections ───────────────────────────────────────────────────────
HCAPTCHA_SITEKEY=
HCAPTCHA_SECRET=
CAPTCHA_ENABLED=0
RATELIMIT_ENABLED=0
RATELIMIT_DEFAULT=200 per day
```

---

## 11. Supabase Setup

1. Create a project at [supabase.com](https://supabase.com/).
2. Open **Project Settings → Database** and copy the PostgreSQL connection string.
3. Set `DATABASE_URL` in `.env` to that connection string.
4. Open **Project Settings → API** and copy `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY`.
5. Put those three values in `.env` as well. The current app boots from `DATABASE_URL`, but keeping the full Supabase project metadata in env keeps deployments and future integrations aligned.
6. Under **Authentication → Providers**, ensure Email is enabled if you plan to extend auth beyond the current Flask-session flow.

> 💡 For production hosting, prefer the Supabase pooler host (`aws-*.pooler.supabase.com`) over the direct database host if your environment has IPv6 or connection-pool constraints.

---

## 12. Cloudinary Setup

1. Create an account at [cloudinary.com](https://cloudinary.com/).
2. Open the dashboard and copy `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET`.
3. Put those values into `.env`.
4. Start the app and generate a reel. Insta Sum uploads assets into this folder structure:

```
insta_sum/
  <username>/
    audio/
      <shortcode>.mp3
    thumbnails/
      <shortcode>.jpg
```

5. The frontend reads `audio_url` and `thumbnail_url` directly from the API payload.

---

## 13. Instagram Fetch Layer Setup

### Layer 1 — Apify *(production)*

- Sign up at [apify.com](https://apify.com/).
- Copy your API token into `APIFY_TOKEN`.
- Insta Sum uses the `apify/instagram-scraper` actor as layer 1.
- This is the production-grade path and should be the default on any public deployment.

> ⚠️ The free tier has a monthly compute cap. If this app is public, budget for a paid plan.

### Layer 2 — Instaloader *(authenticated fallback)*

- Create a dedicated burner Instagram account.
- Set `IG_USERNAME` and `IG_PASSWORD` in `.env`.
- On first successful use, Insta Sum saves `<IG_USERNAME>.session` in the project root and reuses it on later runs.
- If the session becomes stale, the app falls back to a fresh login and overwrites the session.
- `.session` files are ignored by git and should never be committed.

> ⚠️ Do not use your personal Instagram account here. If Instagram challenges the account, you want to burn a disposable login, not your real one.

### Layer 3 — yt-dlp browser cookies *(local dev only)*

- Set `IG_COOKIES_FROM_BROWSER=1`.
- Set `IG_BROWSER` to one or more supported values: `chrome`, `edge`, `firefox`, `safari`, `brave`, `opera`.
- Optionally set `IG_BROWSER_PROFILE` if you are not using the default browser profile.
- This layer only works on machines that have that browser installed and logged into Instagram.

> 💡 `IG_COOKIES_FILE` is still useful for individual reel downloads. The media download path in `app/services/media.py` passes it to yt-dlp when downloading individual reel audio.

---

## 14. Frontend Development

The frontend lives in `frontend/` and is built with Vite. Production builds go directly into `app/static/dist`, and Flask serves that bundle from the SPA catch-all routes.

### Run both servers during development

```bash
# Terminal 1
python run.py

# Terminal 2
cd frontend
npm run dev
```

### Build for production

```bash
npm --prefix frontend run build
# Output: app/static/dist/
```

**Vite proxy targets in dev:**
`/api` · `/auth` · `/dashboard` · `/export` · `/thumbnails` · `/audio` · `/proxy-image`

**All user-facing copy is centralized in:**

```
frontend/src/copy.js
```

That file is the right place to update labels, empty-state text, aria labels, and product copy without digging through JSX.

---

## 15. How It Works — Plain English

You sign in, paste a public Instagram profile, and let Insta Sum pull the reel catalog. The app does not make you wait on a full processing pass before showing anything useful. It fetches metadata first, stores it in Postgres, and renders the profile as a browsable content library.

Once the reels are in, you decide what deserves deeper work. You can generate one reel at a time or queue the whole profile. Search-time fetches already try to improve the UI by precomputing transcript and title data where possible, so you are not staring at a wall of "Untitled Reel" placeholders.

When you generate a reel, the app downloads the media into a temp workspace, extracts audio, runs Whisper locally, and then sends the transcript and caption through OpenAI or Azure OpenAI for a title and structured summary. If the AI path is unavailable, it falls back to Sumy and lightweight heuristics so the job still resolves instead of dead-ending.

The browser never has to reload for results. The React app polls for reel and batch status, updates cards in place, and keeps the full output in the database. Audio and thumbnails live in Cloudinary, so once a reel is processed you can revisit it, search it, and export it without repeating the entire pipeline.

---

## 16. API Endpoints Reference

| Method | Route | Auth required | Description | Response type |
| --- | --- | :---: | --- | --- |
| `GET` | `/` | — | SPA root entry | HTML |
| `GET` | `/dashboard` | — | Home route for the React app | HTML |
| `GET` | `/login` | — | SPA login route | HTML |
| `GET` | `/signup` | — | SPA signup route | HTML |
| `GET` | `/profile/<username>` | — | SPA profile route | HTML |
| `GET` | `/<path>` | — | SPA catch-all for non-API paths | HTML |
| `POST` | `/dashboard/search` | ✅ | Compatibility search route | JSON or redirect |
| `POST` | `/analyze` | ✅ | Compatibility alias for profile search | JSON or redirect |
| `GET` | `/results/<username>` | ✅ | Legacy route redirected into SPA profile view | Redirect |
| `GET` | `/api/config` | ✅ | Frontend config payload (page size, poll defaults) | JSON |
| `GET` | `/api/auth/me` | ✅ | Current authenticated session | JSON |
| `POST` | `/api/auth/login` | — | Login for SPA | JSON |
| `POST` | `/api/auth/signup` | — | Signup for SPA | JSON |
| `POST` | `/api/auth/logout` | ✅ | Logout for SPA | JSON |
| `GET` | `/api/profiles` | ✅ | Recent profile history for the sidebar/home screen | JSON |
| `POST` | `/api/profiles/search` | ✅ | Search a profile and upsert metadata | JSON |
| `GET` | `/api/profiles/<username>` | ✅ | Profile details plus paginated reels | JSON |
| `GET` | `/api/reels/<id>/status` | ✅ | Lightweight reel status payload for polling | JSON |
| `GET` | `/api/jobs/<id>/status` | ✅ | Batch job status payload for polling | JSON |
| `POST` | `/api/reels/<id>/generate` | ✅ | Queue a single reel job | JSON |
| `POST` | `/api/profiles/<id>/generate-all` | ✅ | Queue a batch job for a profile | JSON |
| `GET` | `/api/stream/<job_id>` | ✅ | Compatibility SSE stream | `text/event-stream` |
| `GET` | `/proxy-image?url=...` | ✅ | Proxy external Instagram CDN images | Image |
| `GET` | `/export/profile/<id>?format=json` | ✅ | Export a profile in JSON | JSON download |
| `GET` | `/export/profile/<id>?format=csv` | ✅ | Export a profile in CSV | CSV download |
| `GET` | `/auth/login` | — | Legacy server-handled login page | HTML |
| `POST` | `/auth/login` | — | Legacy server-handled login submit | Redirect |
| `GET` | `/auth/signup` | — | Legacy server-handled signup page | HTML |
| `POST` | `/auth/signup` | — | Legacy server-handled signup submit | Redirect |
| `POST` | `/auth/logout` | ✅ | Legacy server-handled logout | Redirect |

> **Notes:**
> - The current architecture does not expose a dedicated Flask `/audio/...` route. Reel audio is served directly from the Cloudinary `audio_url` stored on each reel.
> - The React frontend uses polling, not SSE, for live job updates.

---

## 17. Whisper Model Selection Guide

| Model | Speed | Accuracy | RAM required | Best for |
| --- | --- | --- | --- | --- |
| `tiny` | ⚡⚡⚡⚡⚡ | ★☆☆☆☆ | ~1 GB | Fast smoke tests only |
| `base` | ⚡⚡⚡⚡ | ★★★☆☆ | ~1 GB | **Default — most users** |
| `small` | ⚡⚡⚡ | ★★★★☆ | ~2 GB | Better accuracy on CPU |
| `medium` | ⚡⚡ | ★★★★☆ | ~5 GB | Higher-quality summaries from tougher audio |
| `large` | ⚡ | ★★★★★ | ~10 GB | GPU-backed installs that want the best transcription |

```bash
# Set in .env
WHISPER_MODEL=base
```

> 💡 If you have CUDA configured, Whisper can shift from "usable" to "comfortable" on larger models very quickly.

---

## 18. Known Limitations

| Limitation | Detail |
| --- | --- |
| **Public accounts only** | Insta Sum cannot access private Instagram accounts |
| **Instagram rate limiting** | Instagram can still throttle requests even with the 3-layer fetch stack |
| **Apify free tier** | Monthly compute cap — budget for a paid plan on any public deployment |
| **Instaloader 429s** | The burner account can hit challenge flows if used too aggressively |
| **yt-dlp profile extractor** | Remains unreliable as of early 2026 — local-dev last resort only |
| **Processing time** | Scales with reel count and audio duration on CPU-only Whisper installs |
| **Cloudinary free tier** | Storage and bandwidth caps apply |
| **Supabase free tier** | Database size and compute caps apply |
| **Google sign-in** | UI-complete, not yet wired to any auth provider |
| **Stale cookies file** | `IG_COOKIES_FILE` needs periodic manual refresh every 2–3 weeks |

---

## 19. Troubleshooting

| Error or symptom | Likely cause | Fix |
| --- | --- | --- |
| `Apify monthly usage limit exceeded` | Free-tier compute cap reached | Upgrade the Apify plan, wait for the next billing cycle, or rely on the Instaloader fallback locally |
| Instaloader `429` or rate-limit errors | Burner account challenged or used too aggressively | Slow down requests, rotate to a different burner account, delete the stale `.session` file, and log in again |
| `yt-dlp extraction failed` on profile fetch | The local browser-cookie fallback is brittle | Treat yt-dlp as last resort only — fix Apify or Instaloader first |
| `Unsupported URL` from yt-dlp | Old metadata path or broken Instagram extractor | Upgrade `yt-dlp` and keep it limited to individual reel downloads only |
| `ffmpeg not found` / `ffprobe not found` | FFmpeg is missing or not on PATH | Install FFmpeg and set `FFMPEG_LOCATION` if needed |
| Cloudinary upload fails | Wrong credentials or blocked network egress | Recheck the three Cloudinary env vars and confirm uploads work from the host machine |
| Supabase connection refused / host resolution errors | Bad `DATABASE_URL`, pooler mismatch, or network/DNS issue | Verify the Supabase connection string and prefer the pooler host in hosted environments |
| `database is locked` | Still pointing at an old local database URL | Set `DATABASE_URL` to Supabase Postgres, restart the app, and remove stale local DB config |
| Audio route 404s (`/audio/...`) | Old frontend bundle expecting legacy local assets | Rebuild the React bundle and hard-refresh the browser |
| Thumbnails do not render | CDN hotlink-blocked or no `thumbnail_url` yet | Use `/proxy-image` for external URLs and confirm the frontend resolves `thumbnail_url` immediately |
| OpenAI summaries fail silently | Missing API key, bad model name, or wrong Azure deployment | Verify `OPENAI_API_KEY` or the Azure env vars — the app will fall back to Sumy but quality drops |
| React white screen on load | Broken SPA build or mismatched static assets | Run `npm --prefix frontend run build` again and restart Flask |
| Vite proxy not forwarding API requests | Flask not running on port `5000` or Vite has stale config | Start Flask first, then restart `npm run dev` |
| Session expired mid-session | Session cookie expired or server restarted with a new secret | Sign in again and keep `SECRET_KEY` stable across restarts |
| Google button does nothing | Not a bug — it is not wired yet | Use email/password auth for now or implement a real provider |

---

## 20. Contributing

### 1 · Fork and branch

```bash
git checkout -b feat/your-change
```

### 2 · Keep commit messages structured

| Prefix | Use for |
| --- | --- |
| `feat:` | New functionality |
| `fix:` | Bug fixes |
| `refactor:` | Internal code cleanup with no intended behavior change |
| `docs:` | Documentation changes |
| `chore:` | Tooling, config, dependency, or maintenance work |

### 3 · Verify both sides locally before opening a PR

```bash
# Backend
python -m compileall app
python run.py

# Frontend
npm --prefix frontend run build
```

### 4 · Pull request checklist

- Clear summary of the change
- Screenshots or recordings for UI changes
- Updated env-var documentation if config changed
- Migration notes if database fields changed

---

## 21. Roadmap

- [ ] Google OAuth wired end-to-end
- [ ] Instagram Stories support
- [ ] Webhook or email notifications for completed batch jobs
- [ ] Public shareable profile report links
- [ ] Team workspaces with shared profile access
- [ ] Browser extension for one-click profile analysis

---

## 22. License

```
MIT License

Copyright (c) 2026 Faizan Tanveer

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 23. Acknowledgements

| Project | Role in Insta Sum | Link |
| --- | --- | --- |
| Flask | Backend application framework | [flask.palletsprojects.com](https://flask.palletsprojects.com/) |
| SQLAlchemy | ORM and database layer | [sqlalchemy.org](https://www.sqlalchemy.org/) |
| Supabase | Managed PostgreSQL hosting | [supabase.com](https://supabase.com/) |
| Cloudinary Python SDK | Media uploads and delivery URLs | [cloudinary.com/documentation](https://cloudinary.com/documentation/python_integration) |
| OpenAI Whisper | Local transcription engine | [github.com/openai/whisper](https://github.com/openai/whisper) |
| yt-dlp | Reel media extraction and fallback browser-cookie access | [github.com/yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) |
| Instaloader | Authenticated Instagram metadata fallback | [instaloader.github.io](https://instaloader.github.io/) |
| Apify Client | Primary production Instagram fetch integration | [docs.apify.com](https://docs.apify.com/api/client/python) |
| OpenAI Python SDK | Standard OpenAI and Azure client integration | [github.com/openai/openai-python](https://github.com/openai/openai-python) |
| React | SPA rendering layer | [react.dev](https://react.dev/) |
| Vite | Frontend build tool and dev server | [vitejs.dev](https://vitejs.dev/) |
| React Router | Client-side routing | [reactrouter.com](https://reactrouter.com/) |
| Lucide React | Icon set | [lucide.dev](https://lucide.dev/) |
| Sumy | Offline summary fallback | [github.com/miso-belica/sumy](https://github.com/miso-belica/sumy) |
| NLTK | Tokenization support for fallback NLP paths | [nltk.org](https://www.nltk.org/) |
| python-dotenv | `.env` loading | [github.com/theskumar/python-dotenv](https://github.com/theskumar/python-dotenv) |

---

<div align="center">

Built by <a href="https://github.com/faizantanveeer">Faizan Tanveer</a>

<br />

<em>If Insta Sum saves you time, consider giving it a ⭐ on GitHub.</em>

</div>