<div align="center">

<br/>

```
██╗███╗   ██╗███████╗████████╗ █████╗     ███████╗██╗   ██╗███╗   ███╗
██║████╗  ██║██╔════╝╚══██╔══╝██╔══██╗    ██╔════╝██║   ██║████╗ ████║
██║██╔██╗ ██║███████╗   ██║   ███████║    ███████╗██║   ██║██╔████╔██║
██║██║╚██╗██║╚════██║   ██║   ██╔══██║    ╚════██║██║   ██║██║╚██╔╝██║
██║██║ ╚████║███████║   ██║   ██║  ██║    ███████║╚██████╔╝██║ ╚═╝ ██║
╚═╝╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚═╝  ╚═╝    ╚══════╝ ╚═════╝ ╚═╝     ╚═╝
```

**Any account · Every reel · Instant insight**

<br/>

[![Python](https://img.shields.io/badge/Python_3.9+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask_3.0-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![React](https://img.shields.io/badge/React_18-20232A?style=flat-square&logo=react&logoColor=61DAFB)](https://react.dev)
[![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=flat-square&logo=supabase&logoColor=white)](https://supabase.com)
[![License](https://img.shields.io/badge/MIT-111111?style=flat-square)](LICENSE)
[![Status](https://img.shields.io/badge/Active-1DB954?style=flat-square)]()

<br/>

> Turn any public Instagram profile into a **searchable, exportable content library.**
> Paste a username → browse every reel → generate AI transcripts and summaries — without watching a single video.

<br/>

[**Get Started**](#-installation) · [**How It Works**](#-how-it-works) · [**Configuration**](#-configuration) · [**API**](#-api-reference)

<br/>

</div>

---

## ✦ What It Does

You paste a public Instagram username. Insta Sum fetches the full reel catalog, stores it in Postgres, and gives you a browsable content library in seconds.

From there, you can generate AI-powered titles, transcripts, and summaries — one reel at a time or for an entire profile in a single batch. Everything is searchable, filterable, and exportable.

No refreshing. No waiting. The React frontend polls for updates and rewrites cards in place as jobs complete in the background.

---

## ✦ Features

**Backend**
- 3-layer Instagram fetch — Apify → Instaloader → yt-dlp browser-cookie fallback
- Local Whisper transcription (configurable model size, CPU/GPU)
- AI summaries via OpenAI or Azure OpenAI, with Sumy offline fallback
- Background worker threads — batch jobs never block the UI
- PostgreSQL full-text search with TSVECTOR + GIN index
- JSON and CSV export for any analyzed profile
- Cloudinary storage for audio and thumbnails

**Frontend**
- React SPA with React Router — no page reloads
- Live polling for reel and batch job status
- Grid and list layouts with keyword, status, and sort filtering
- Reel detail modal with summary, transcript, metadata, and audio playback
- Light/dark monochrome themes with persistent preference
- Toast notifications throughout

---

## ✦ Architecture

```
Browser (React SPA)
    │  same-origin fetch + session cookie
    ▼
Flask  ──────────────────────────────────────────────┐
  │  /api/auth/*          Authentication             │
  │  /api/profiles/*      Profile + reel data        │ Supabase
  │  /api/reels/*         Status polling             │ PostgreSQL
  │  /api/jobs/*          Batch job tracking         │
  │  /export/*            JSON / CSV download        │
  │                                                  │
  ├── Instagram Service ──────────────────────────   │
  │     1. Apify (production)                        │
  │     2. Instaloader (authenticated fallback)      │
  │     3. yt-dlp browser cookies (local dev)        │
  │                                                  │
  └── Processing Pipeline ─────────────────────────  │
        yt-dlp download → Whisper → OpenAI/Azure     │
        → Cloudinary upload → write to Postgres ─────┘
```

---

## ✦ Processing Pipeline

```
User clicks "Generate"
        │
        ▼
  Job row created, worker thread starts
        │
        ├─ Reel already processed? → skip
        │
        ▼
  yt-dlp downloads reel audio to /tmp
        │
        ├─ Download fails? → fail reel, persist error
        │
        ▼
  Whisper transcribes audio locally
        │
        ├─ No speech detected? → store note, continue
        │
        ▼
  Generate title + summary
        │
        ├─ Azure OpenAI configured? → use Azure
        ├─ OpenAI key set?          → use OpenAI
        └─ Neither?                 → Sumy + heuristics
        │
        ▼
  Upload audio + thumbnail to Cloudinary
        │
        ▼
  Write results to Postgres
        │
        ▼
  React polling detects completion → card updates in place
```

---

## ✦ Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, React Router 6, Vite 5, Lucide React |
| Backend | Flask 3, SQLAlchemy 2, Werkzeug, Flask-Limiter |
| Database | Supabase PostgreSQL (TSVECTOR + GIN full-text search) |
| Media | Cloudinary (audio + thumbnails), yt-dlp (reel extraction) |
| Instagram | Apify · Instaloader · yt-dlp browser cookies |
| Transcription | OpenAI Whisper (local), configurable model size |
| Summarization | OpenAI / Azure OpenAI → Sumy fallback |
| Auth | Flask sessions, Werkzeug password hashing |

---

## ✦ Prerequisites

- **Python 3.9+**
- **Node.js 18+**
- **FFmpeg** (mandatory — reel download and Whisper preprocessing will fail without it)

```bash
# macOS
brew install python@3.11 node ffmpeg

# Ubuntu / Debian
sudo apt-get install -y python3 python3-venv nodejs npm ffmpeg

# Windows
winget install Python.Python.3.11 OpenJS.NodeJS.LTS Gyan.FFmpeg
```

---

## ✦ Installation

```bash
# 1. Clone
git clone https://github.com/faizantanveeer/InstaSum.git
cd InstaSum

# 2. Python environment
python3 -m venv .venv && source .venv/bin/activate

# 3. Dependencies
pip install -r requirements.txt
npm --prefix frontend install

# 4. Environment
cp .env.example .env
# → fill in DATABASE_URL, Cloudinary, Apify, OpenAI (see Configuration below)

# 5. Database
python -c "from app import create_app; create_app(); print('Done')"

# 6. Build frontend
npm --prefix frontend run build

# 7. Run
python run.py
```

Open `http://127.0.0.1:5000`

**Dev mode (hot reload):**
```bash
# Terminal 1
python run.py

# Terminal 2
cd frontend && npm run dev   # → http://127.0.0.1:5173
```

Vite proxies `/api`, `/auth`, `/export`, `/proxy-image`, and `/dashboard` back to Flask automatically.

---

## ✦ Configuration

### Minimum viable `.env`

```bash
# Required
SECRET_KEY=your-random-secret
DATABASE_URL=postgresql://...          # Supabase connection string

# Cloudinary (required for media storage)
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=

# At least one Instagram fetch layer
APIFY_TOKEN=                           # Recommended for production

# At least one summarization path
OPENAI_API_KEY=                        # Falls back to Sumy if omitted
```

### Full reference

<details>
<summary><strong>Flask & App</strong></summary>

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-secret` | Flask session signing key |
| `FLASK_ENV` | `development` | Runtime mode |
| `DATABASE_URL` | — | SQLAlchemy connection string |
| `PAGE_SIZE` | `12` | Default pagination size |
| `MAX_REELS` | `100` | Max reels fetched per profile |
| `TEMP_DIR` | `./tmp` | Temp workspace for media processing |

</details>

<details>
<summary><strong>Instagram Fetch Layers</strong></summary>

| Variable | Description |
|---|---|
| `APIFY_TOKEN` | Primary production fetcher (recommended) |
| `IG_USERNAME` / `IG_PASSWORD` | Burner account for Instaloader fallback |
| `IG_COOKIES_FILE` | Netscape cookies file for yt-dlp media downloads |
| `IG_COOKIES_FROM_BROWSER` | `1` to enable browser-cookie fallback (local dev only) |
| `IG_BROWSER` | Browser to extract cookies from, e.g. `chrome,edge` |
| `PROFILE_CACHE_MINUTES` | `60` — metadata freshness window |

> ⚠️ Never use your personal Instagram account. Use a dedicated burner.

</details>

<details>
<summary><strong>AI & Transcription</strong></summary>

| Variable | Default | Description |
|---|---|---|
| `WHISPER_MODEL` | `base` | Local Whisper model size |
| `OPENAI_API_KEY` | — | Standard OpenAI |
| `OPENAI_SUMMARY_MODEL` | `gpt-4o-mini` | Model for titles and summaries |
| `AZURE_OPENAI_ENDPOINT` | — | Azure OpenAI endpoint |
| `AZURE_OPENAI_API_KEY` | — | Azure API key |
| `AZURE_OPENAI_DEPLOYMENT` | — | Azure deployment name |

</details>

<details>
<summary><strong>Complete `.env.example`</strong></summary>

```bash
SECRET_KEY=
FLASK_ENV=development
DATABASE_URL=

OPENAI_API_KEY=
OPENAI_SUMMARY_MODEL=gpt-4o-mini
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT=

WHISPER_MODEL=base
FFMPEG_LOCATION=
DISABLE_LOCAL_WHISPER=0

SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=

APIFY_TOKEN=
IG_USERNAME=
IG_PASSWORD=
IG_COOKIES_FILE=./instagram_cookies.txt
IG_COOKIES_FROM_BROWSER=0
IG_BROWSER=edge,chrome
PROFILE_CACHE_MINUTES=60
FETCH_TIMEOUT_SECONDS=180

MAX_REELS=100
PAGE_SIZE=12
TEMP_DIR=./tmp

RATELIMIT_ENABLED=0
CAPTCHA_ENABLED=0
EXPORT_MAX_ROWS=5000
```

</details>

---

## ✦ Service Setup

### Supabase
1. Create a project at [supabase.com](https://supabase.com)
2. Copy the PostgreSQL connection string from **Project Settings → Database**
3. Set it as `DATABASE_URL` in `.env`

### Cloudinary
1. Create an account at [cloudinary.com](https://cloudinary.com)
2. Copy `Cloud Name`, `API Key`, and `API Secret` from the dashboard
3. Assets are stored under `insta_sum/<username>/audio/` and `.../thumbnails/`

### Instagram — Pick your layer

| Layer | When to use | Setup |
|---|---|---|
| **Apify** | Production | Set `APIFY_TOKEN`. Uses `apify/instagram-scraper`. |
| **Instaloader** | Authenticated fallback | Set `IG_USERNAME` + `IG_PASSWORD` (burner account). Session file auto-saved. |
| **yt-dlp cookies** | Local dev only | Set `IG_COOKIES_FROM_BROWSER=1` + `IG_BROWSER`. Requires browser to be logged into Instagram. |

---

## ✦ Whisper Models

| Model | Speed | Accuracy | RAM |
|---|---|---|---|
| `tiny` | ⚡⚡⚡⚡⚡ | ★☆☆☆☆ | ~1 GB |
| `base` | ⚡⚡⚡⚡ | ★★★☆☆ | ~1 GB — **default** |
| `small` | ⚡⚡⚡ | ★★★★☆ | ~2 GB |
| `medium` | ⚡⚡ | ★★★★☆ | ~5 GB |
| `large` | ⚡ | ★★★★★ | ~10 GB |

`base` is the right default for most CPU installs. If you have a GPU and CUDA configured, `medium` or `large` becomes practical.

---

## ✦ API Reference

<details>
<summary><strong>Auth</strong></summary>

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/auth/me` | Current session |
| `POST` | `/api/auth/login` | Login |
| `POST` | `/api/auth/signup` | Signup |
| `POST` | `/api/auth/logout` | Logout |

</details>

<details>
<summary><strong>Profiles & Reels</strong></summary>

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/profiles` | Recent profile history |
| `POST` | `/api/profiles/search` | Search a profile, upsert metadata |
| `GET` | `/api/profiles/<username>` | Profile + paginated reels |
| `GET` | `/api/reels/<id>/status` | Reel status (poll this) |
| `POST` | `/api/reels/<id>/generate` | Queue single reel job |
| `POST` | `/api/profiles/<id>/generate-all` | Queue batch job |
| `GET` | `/api/jobs/<id>/status` | Batch job status (poll this) |

</details>

<details>
<summary><strong>Export & Utilities</strong></summary>

| Method | Route | Description |
|---|---|---|
| `GET` | `/export/profile/<id>?format=json` | Export profile as JSON |
| `GET` | `/export/profile/<id>?format=csv` | Export profile as CSV |
| `GET` | `/proxy-image?url=...` | Proxy Instagram CDN images |
| `GET` | `/api/config` | Frontend config (page size, poll intervals) |

</details>

---

## ✦ Known Limitations

| Issue | Detail |
|---|---|
| Public accounts only | Private profiles cannot be accessed |
| Instagram rate limiting | Can affect all three fetch layers |
| Apify free tier | Monthly compute cap — plan for paid on public deployments |
| Processing time | Scales with audio duration on CPU Whisper installs |
| Google sign-in | UI exists, not yet wired to a provider |
| Cookie file staleness | `IG_COOKIES_FILE` needs manual refresh every 2–3 weeks |

---

## ✦ Troubleshooting

| Symptom | Fix |
|---|---|
| `ffmpeg not found` | Install FFmpeg and set `FFMPEG_LOCATION` if not on PATH |
| Apify monthly limit hit | Wait for billing cycle, upgrade plan, or use Instaloader locally |
| Instaloader 429 errors | Delete stale `.session` file, slow down, rotate burner account |
| Cloudinary upload fails | Recheck the three Cloudinary env vars |
| Supabase connection refused | Verify `DATABASE_URL` — prefer the pooler host in hosted environments |
| React white screen | Run `npm --prefix frontend run build` and restart Flask |
| Summaries falling back to Sumy | Check `OPENAI_API_KEY` or Azure env vars |
| Session expires mid-use | Sign in again; keep `SECRET_KEY` stable across restarts |

---

## ✦ Roadmap

- [ ] Google OAuth
- [ ] Instagram Stories support
- [ ] Webhook / email notifications for completed batch jobs
- [ ] Public shareable profile report links
- [ ] Team workspaces

---

## ✦ Contributing

```bash
git checkout -b feat/your-change
```

Commit prefix conventions: `feat:` · `fix:` · `refactor:` · `docs:` · `chore:`

Before opening a PR: verify both `python run.py` and `npm --prefix frontend run build` pass cleanly. Include screenshots for UI changes and migration notes if the database schema changed.

---

## ✦ License

MIT © 2026 [Faizan Tanveer](https://github.com/faizantanveeer)

---

## ✦ Acknowledgements

[Flask](https://flask.palletsprojects.com) · [SQLAlchemy](https://sqlalchemy.org) · [Supabase](https://supabase.com) · [Cloudinary](https://cloudinary.com) · [OpenAI Whisper](https://github.com/openai/whisper) · [yt-dlp](https://github.com/yt-dlp/yt-dlp) · [Instaloader](https://instaloader.github.io) · [Apify](https://docs.apify.com) · [React](https://react.dev) · [Vite](https://vitejs.dev) · [Sumy](https://github.com/miso-belica/sumy)

---

<div align="center">

*If Insta Sum saves you time, a ⭐ goes a long way.*

</div>