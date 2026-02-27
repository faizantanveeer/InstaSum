# Insta Sum
*Fetch, transcribe, and summarize Instagram Reels from public accounts with on-demand AI processing.*

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0.2-000000?logo=flask&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

## 1. Hero Header

Insta Sum is a Flask application for analyzing public Instagram Reel content in a structured workspace. Users search a profile once to load metadata and thumbnails, then choose exactly which reels to process using per-reel or batch generation actions. The app downloads audio, runs local Whisper transcription, and generates detailed AI summaries with OpenAI or Azure OpenAI, while streaming live job updates over SSE. It is designed for marketers, researchers, and content teams who need searchable, exportable reel intelligence without manually watching every video.

---

## 2. Table of Contents
- [3. Features](#3-features)
- [4. System Architecture Diagram](#4-system-architecture-diagram)
- [5. Processing Pipeline Flowchart](#5-processing-pipeline-flowchart)
- [6. Tech Stack](#6-tech-stack)
- [7. Project Structure](#7-project-structure)
- [8. Prerequisites](#8-prerequisites)
- [9. Installation and Setup](#9-installation-and-setup)
- [10. Environment Variables](#10-environment-variables)
- [11. Instagram Cookies Setup](#11-instagram-cookies-setup)
- [12. API Keys Setup](#12-api-keys-setup)
- [13. How It Works (Plain English)](#13-how-it-works-plain-english)
- [14. API Endpoints Reference](#14-api-endpoints-reference)
- [15. Whisper Model Selection Guide](#15-whisper-model-selection-guide)
- [16. Known Limitations](#16-known-limitations)
- [17. Troubleshooting](#17-troubleshooting)
- [18. Contributing](#18-contributing)
- [19. License](#19-license)
- [20. Acknowledgements](#20-acknowledgements)

---

## 3. Features
- Local email/password authentication with user-isolated data access.
- Single dashboard workspace with profile search at the top.
- Accepts Instagram username, `@username`, or full profile URL.
- Metadata-first search flow:
  - fetches profile info and reel metadata/thumbnails,
  - does not auto-transcribe on search.
- Three-layer reel discovery fallback:
  - RapidAPI (primary),
  - yt-dlp with cookies (secondary),
  - Apify actor (tertiary).
- Per-reel `Generate` and `Regenerate` controls.
- Profile-level `Generate All` and `Regenerate All` controls.
- Background processing jobs with live Server-Sent Events (SSE) progress.
- Local media pipeline:
  - reel audio download (deduped),
  - thumbnail download (deduped),
  - filesystem organization under `downloads/<username>/audio` and `downloads/<username>/thumbnails`.
- Local Whisper transcription (offline speech-to-text).
- AI summary generation with OpenAI Chat Completions:
  - supports standard OpenAI API key flow,
  - supports Azure OpenAI deployment flow.
- Built-in fallback summarizer (`sumy`) when AI API is unavailable.
- Detailed summary storage plus preview summary.
- In-card transcript and detailed summary toggle views.
- Local audio playback from secure app routes.
- Thumbnail proxy route for CDN-restricted image embeds.
- CSV and JSON export for the active profile.
- SQLite persistence with SQLAlchemy and FTS search index support.
- SQLite lock mitigation:
  - WAL mode,
  - busy timeout,
  - commit retry logic in critical paths.

---

## 4. System Architecture Diagram
```text
+------------------------------------------------------------------------------+
¦                                USER BROWSER                                 ¦
¦                                                                              ¦
¦  /auth/login or /auth/signup  -->  /dashboard                               ¦
¦  Search profile (metadata only) --> Generate one reel or generate all       ¦
¦  SSE updates on /api/stream/<job_id> and incremental card refresh           ¦
+------------------------------------------------------------------------------+
                                ¦ HTTP + SSE
                                ?
+------------------------------------------------------------------------------+
¦                               FLASK SERVER                                  ¦
¦                                                                              ¦
¦  Main Routes                                                                 ¦
¦  GET  /                    -> redirect to login or dashboard                 ¦
¦  GET  /dashboard           -> render workspace                               ¦
¦  POST /dashboard/search    -> fetch profile + reels metadata                ¦
¦                                                                              ¦
¦  Auth Routes                                                                 ¦
¦  GET/POST /auth/login      -> sign in                                       ¦
¦  GET/POST /auth/signup     -> register                                      ¦
¦  POST     /auth/logout     -> sign out                                      ¦
¦                                                                              ¦
¦  API Routes                                                                  ¦
¦  POST /api/reels/<id>/generate                 -> queue single reel job      ¦
¦  POST /api/profiles/<id>/generate-all          -> queue batch job            ¦
¦  GET  /api/stream/<job_id>                     -> SSE progress/events        ¦
¦  GET  /thumbnails/<username>/<path:filename>   -> local thumbnail serving    ¦
¦  GET  /audio/<username>/<path:filename>        -> local audio serving        ¦
¦  GET  /proxy-image?url=<cdn_url>               -> thumbnail proxy            ¦
¦  GET  /export/profile/<id>?format=csv|json     -> profile export             ¦
+------------------------------------------------------------------------------+
                       ¦                       ¦
                       ?                       ?
+----------------------------+       +-----------------------------------------+
¦      FETCH LAYER           ¦       ¦            PROCESSING LAYER             ¦
¦                            ¦       ¦                                         ¦
¦  InstagramService          ¦       ¦  media.py                               ¦
¦  1) RapidAPI               ¦       ¦   - download_reel_audio()              ¦
¦  2) yt-dlp + cookies       ¦       ¦   - download_reel_thumbnail()          ¦
¦  3) Apify actor            ¦       ¦                                         ¦
¦                            ¦       ¦  transcription.py                       ¦
¦                            ¦       ¦   - local Whisper model                ¦
¦                            ¦       ¦                                         ¦
¦                            ¦       ¦  summarization.py                       ¦
¦                            ¦       ¦   - OpenAI or Azure OpenAI             ¦
¦                            ¦       ¦   - sumy fallback                       ¦
+----------------------------+       +-----------------------------------------+
                                                            ¦
                                                            ?
                                       +---------------------------------------+
                                       ¦             STORAGE LAYER             ¦
                                       ¦                                       ¦
                                       ¦ SQLite + SQLAlchemy                   ¦
                                       ¦ - users                               ¦
                                       ¦ - profiles                            ¦
                                       ¦ - jobs                                ¦
                                       ¦ - reels                               ¦
                                       ¦ - reel_errors                         ¦
                                       ¦ - reel_fts (FTS5)                     ¦
                                       ¦                                       ¦
                                       ¦ Filesystem downloads/                 ¦
                                       ¦ - <username>/audio/*.mp3              ¦
                                       ¦ - <username>/thumbnails/*.jpg         ¦
                                       +---------------------------------------+
```

---

## 5. Processing Pipeline Flowchart
```text
[User submits profile input on /dashboard]
        |
        v
[Normalize username/url in utils.normalize_username]
        |
        v
{Username valid?}
  | no ------------------------> [Flash error + redirect /dashboard] --> [END]
  |
 yes
  |
  v
[InstagramService.fetch_reels(username)]
  |
  v
{RapidAPI success?}
  | yes
  v
[Use RapidAPI results]
  |
  no
  |
  v
{yt-dlp metadata success?}
  | yes
  v
[Use yt-dlp results]
  |
  no
  |
  v
{Apify success?}
  | yes
  v
[Use Apify results]
  |
  no --------------------------------> [Flash fetch failure + redirect] --> [END]

[Upsert profile + reel metadata for current user]
        |
        v
{Profile private/inaccessible?}
  | yes -----------------------> [Set private flag + flash error + redirect] --> [END]
  |
  no
  |
  v
[Attempt thumbnail download if local thumbnail missing]
        |
        v
[Render dashboard with reel cards (pending status)]
        |
        v
[User clicks Generate or Generate All]
        |
        v
[Create Job row (single or batch)]
        |
        v
[Start background thread _process_job(...)]
        |
        v
[Open SSE on /api/stream/<job_id>]
        |
        v
[Emit progress: Starting processing]
        |
        v
<Loop each targeted reel>
    |
    v
  {Already processed and regenerate not requested?}
    | yes --> [Mark skipped, update counters, emit reel_update/progress] --> next reel
    |
    no
    |
    v
  [Resolve existing local audio path]
    |
    v
  {Audio exists?}
    | no
    v
  [download_reel_audio via yt-dlp (+ ffmpeg if available)]
    |
    v
  {Audio missing/invalid after download?}
    | yes --> [Mark reel failed + error_reason, emit update] --> next reel
    |
    no
    |
    v
  [Transcribe audio with Whisper]
    |
    v
  {Transcript has speech text?}
    | no --> [Set transcript="No spoken content detected."]
    | yes -> [Store transcript]
    |
    v
  [Generate title + detailed summary (OpenAI/Azure; fallback sumy)]
    |
    v
  [Set processed=true, status=completed, update FTS]
    |
    v
  [Emit reel_update + progress]
    |
    v
[After loop: finalize job status]
        |
        v
{Any success/failed combinations}
  | success only -> [status=completed]
  | mixed         -> [status=partial_failed]
  | failed only   -> [status=failed]
        |
        v
[Emit complete/error SSE]
        |
        v
[Frontend updates cards and status bar]
        |
        v
[END]
```

---

## 6. Tech Stack
| Category | Technology | Purpose |
|---|---|---|
| Backend Framework | Flask 3.x | Routing, templates, API endpoints |
| ORM / Data Layer | SQLAlchemy 2.x | Models, queries, persistence |
| DB Engine | SQLite | Lightweight persistent storage |
| Search Index | SQLite FTS5 | Transcript/summary full-text indexing |
| Auth | Werkzeug security + Flask session | Local email/password auth and session handling |
| Rate Limiting | Flask-Limiter (optional) | Request throttling in production |
| Instagram Fetching | RapidAPI Instagram Scraper | Primary metadata source |
| Instagram Fetching | yt-dlp | Fallback metadata source + media download |
| Instagram Fetching | Apify Instagram actor | Third fallback metadata source |
| Media Processing | ffmpeg/ffprobe | Audio extraction and media postprocessing |
| Transcription | openai-whisper (local) | Offline speech-to-text |
| AI Summarization | OpenAI Chat Completions | Title + detailed summary generation |
| AI Summarization | Azure OpenAI (optional) | Enterprise-hosted model endpoint |
| Fallback Summarization | sumy + nltk | Offline fallback summarization |
| HTTP Clients | requests, httpx | External service calls |
| Frontend | Jinja2 + HTML/CSS + Vanilla JS | Dashboard UI and interactions |
| Live Updates | Server-Sent Events (SSE) | Job progress stream |
| Config Management | python-dotenv | `.env` loading and config |

---

## 7. Project Structure
```text
Insta Sum/
+-- app/
¦   +-- __init__.py                  # Flask app factory, blueprint registration, env loading
¦   +-- config.py                    # Central configuration from environment variables
¦   +-- db.py                        # SQLAlchemy engine/session init, schema guards, FTS helpers
¦   +-- extensions.py                # Flask-Limiter extension setup
¦   +-- models.py                    # SQLAlchemy models: User/Profile/Job/Reel/ReelError
¦   +-- routes/
¦   ¦   +-- main.py                  # Dashboard page routes and profile search flow
¦   ¦   +-- auth.py                  # Login/signup/logout routes
¦   ¦   +-- api.py                   # Generate endpoints, SSE, media serving, export, proxy
¦   +-- services/
¦   ¦   +-- auth.py                  # current_user(), login_required(), session helpers
¦   ¦   +-- instagram.py             # 3-layer reel metadata fetch strategy
¦   ¦   +-- media.py                 # Audio/thumbnail download + dedup + ffmpeg detection
¦   ¦   +-- transcription.py         # Whisper model loading and transcription service
¦   ¦   +-- summarization.py         # OpenAI/Azure summary generation + local fallback
¦   ¦   +-- captcha.py               # hCaptcha verification helper
¦   ¦   +-- jobs.py                  # Legacy worker loop utilities (thread-based)
¦   ¦   +-- utils.py                 # Normalization and utility functions
¦   +-- static/
¦   ¦   +-- styles.css               # App styles
¦   ¦   +-- app.js                   # UI interactions, SSE client, filters/sorting
¦   +-- templates/
¦       +-- base.html                # Shared layout shell
¦       +-- auth_login.html          # Login page
¦       +-- auth_signup.html         # Signup page
¦       +-- dashboard.html           # Main workspace page
¦       +-- index.html               # Legacy template
¦       +-- profile.html             # Legacy template
¦       +-- results.html             # Legacy template
¦       +-- results_user.html        # Legacy template
¦       +-- partials/
¦           +-- reel_card.html       # Reel card UI and actions
¦           +-- reel_list.html       # Legacy list partial
¦           +-- progress.html        # Progress UI partial
+-- downloads/                       # Local media cache (gitignored)
¦   +-- <instagram_username>/
¦       +-- audio/                   # Downloaded reel audio files
¦       +-- thumbnails/              # Downloaded/recovered reel thumbnails
+-- tmp/                             # Temporary files and optional cache artifacts
+-- run.py                           # Runtime entry point
+-- requirements.txt                 # Python dependencies
+-- insta_sum.db                     # SQLite database (generated)
+-- .env                             # Local environment variables (private)
+-- .gitignore                       # Excludes env, db, downloads, temp artifacts
+-- README.md                        # Project documentation
```

---

## 8. Prerequisites
- Python `3.9+` (recommended `3.10` or newer).
- `pip`.
- `Git`.
- `ffmpeg` and `ffprobe` available in PATH, or configured by `FFMPEG_LOCATION`.

### Install prerequisites
#### Windows (PowerShell)
```bash
winget install Git.Git
winget install Python.Python.3.11
winget install Gyan.FFmpeg
```

#### macOS (Homebrew)
```bash
brew install git python ffmpeg
```

#### Ubuntu / Debian
```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip ffmpeg
```

> ?? Warning: Without `ffmpeg` and `ffprobe`, audio extraction/transcription will fail.

---

## 9. Installation and Setup
### 1. Clone the repository
```bash
git clone <your-repo-url>
cd "Insta Sum"
```

### 2. Create and activate a virtual environment
#### Windows (PowerShell)
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### 4. Create `.env`
```bash
copy .env.example .env
```
If `copy` does not work, create `.env` manually and paste the values from the `.env.example` block in this README.

### 5. Configure required variables
- At minimum, set one working fetch path:
  - `RAPIDAPI_KEY`, or
  - `APIFY_TOKEN`, or
  - `IG_COOKIES_FILE` for yt-dlp fallback.
- For AI summaries:
  - set `OPENAI_API_KEY` (OpenAI), or
  - set Azure OpenAI variables (`AZURE_OPENAI_*`).

### 6. Initialize database
Database schema is created automatically on app startup. Optional explicit initialization:
```bash
python -c "from app import create_app; create_app(); print('Database initialized')"
```

### 7. Add Instagram cookies file (recommended)
Place `instagram_cookies.txt` in project root and set:
```bash
IG_COOKIES_FILE=./instagram_cookies.txt
```

### 8. Run the app
```bash
python run.py
```

App URL:
- `http://127.0.0.1:5000`

> ?? Tip: In local development, keep `RATELIMIT_ENABLED=0` to avoid self-throttling during testing.

---

## 10. Environment Variables
### Variable reference
| Variable | Required | Description | Where to get / decide |
|---|---|---|---|
| `SECRET_KEY` | Recommended | Flask session secret | Generate locally (`python -c "import secrets; print(secrets.token_hex(32))"`) |
| `FLASK_ENV` | Optional | `development` or `production` config selection | Local choice |
| `DATABASE_URL` | Optional | SQLAlchemy DB URI (default SQLite) | Local choice |
| `SESSION_COOKIE_SAMESITE` | Optional | Cookie SameSite mode (`Lax` default) | Local choice |
| `SESSION_COOKIE_SECURE` | Optional | Set `1` in HTTPS production | Local choice |
| `OPENAI_API_KEY` | Optional* | OpenAI API key for summarization | https://platform.openai.com/api-keys |
| `OPENAI_SUMMARY_MODEL` | Optional | Model for summary generation (`gpt-4o-mini` default) | OpenAI model choice |
| `OPENAI_WHISPER_MODEL` | Optional | Reserved Whisper API model name (not used by local Whisper path) | OpenAI model docs |
| `AZURE_OPENAI_ENDPOINT` | Optional* | Azure OpenAI endpoint URL | Azure Portal |
| `AZURE_OPENAI_API_KEY` | Optional* | Azure OpenAI API key | Azure Portal |
| `AZURE_OPENAI_API_VERSION` | Optional | Azure API version (`2024-12-01-preview`) | Azure docs |
| `AZURE_OPENAI_DEPLOYMENT` | Optional* | Azure deployment name to call | Azure OpenAI Studio |
| `RAPIDAPI_KEY` | Optional* | Primary Instagram fetch provider key | https://rapidapi.com |
| `APIFY_TOKEN` | Optional* | Third-layer fetch provider token | https://console.apify.com/account/integrations |
| `IG_COOKIES_FILE` | Optional* | Cookies file path for yt-dlp fallback | Export from logged-in browser |
| `PROFILE_CACHE_MINUTES` | Optional | Local profile cache interval | Local choice |
| `DOWNLOADS_DIR` | Optional | Base folder for audio/thumbnails | Local choice |
| `WHISPER_MODEL` | Optional | Local Whisper model (`base` default) | Whisper model preference |
| `FFMPEG_LOCATION` | Optional | Explicit ffmpeg folder/executable path | Local system path |
| `MAX_REELS` | Optional | Max reels fetched per profile | Local performance tradeoff |
| `MAX_REEL_SECONDS` | Optional | Skip reels longer than this duration | Local cost/latency tradeoff |
| `CACHE_TTL_HOURS` | Optional | Cache TTL tuning | Local choice |
| `PAGE_SIZE` | Optional | Pagination size tuning | Local choice |
| `RATELIMIT_DEFAULT` | Optional | Flask-Limiter default rule | Local choice |
| `RATELIMIT_ENABLED` | Optional | Enable rate limiting (`0`/`1`) | Local choice |
| `HCAPTCHA_SITEKEY` | Optional | hCaptcha public site key | https://dashboard.hcaptcha.com |
| `HCAPTCHA_SECRET` | Optional | hCaptcha secret key | https://dashboard.hcaptcha.com |
| `CAPTCHA_ENABLED` | Optional | Enable captcha checks (`0`/`1`) | Local choice |
| `TEMP_DIR` | Optional | Temporary directory path | Local choice |
| `FETCH_RETRY_MAX` | Optional | Fetch retry count | Local tuning |
| `FETCH_RETRY_BASE` | Optional | Exponential backoff base | Local tuning |
| `WORKER_POLL_SECONDS` | Optional | Worker polling interval | Local tuning |
| `STALE_JOB_MINUTES` | Optional | Stale job requeue threshold | Local tuning |
| `STATUS_POLL_SECONDS` | Optional | Legacy status polling interval | Local tuning |
| `LIST_POLL_SECONDS` | Optional | Legacy list polling interval | Local tuning |
| `EXPORT_MAX_ROWS` | Optional | Export row limit | Local tuning |
| `DISABLE_LOCAL_WHISPER` | Optional | Toggle local whisper path (`0`/`1`) | Local choice |

\* You need at least one working metadata source (`RAPIDAPI_KEY` or `APIFY_TOKEN` or valid `IG_COOKIES_FILE`) and at least one summary path (`OPENAI_API_KEY` or Azure OpenAI variables). If no summary API key is set, local `sumy` fallback is used.

### `.env.example`
```bash
# Flask / App
FLASK_ENV=development
SECRET_KEY=change-me
DATABASE_URL=sqlite:///insta_sum.db
SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_SECURE=0

# OpenAI (standard)
OPENAI_API_KEY=
OPENAI_SUMMARY_MODEL=gpt-4o-mini
OPENAI_WHISPER_MODEL=whisper-1

# Azure OpenAI (optional alternative to OPENAI_API_KEY)
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT=

# Instagram fetchers
RAPIDAPI_KEY=
APIFY_TOKEN=
IG_COOKIES_FILE=./instagram_cookies.txt
PROFILE_CACHE_MINUTES=60

# Processing / media
DOWNLOADS_DIR=./downloads
TEMP_DIR=./tmp
WHISPER_MODEL=base
FFMPEG_LOCATION=
MAX_REELS=100
MAX_REEL_SECONDS=180
CACHE_TTL_HOURS=24

# Rate limiting
RATELIMIT_ENABLED=0
RATELIMIT_DEFAULT=200 per day

# Captcha (optional)
CAPTCHA_ENABLED=0
HCAPTCHA_SITEKEY=
HCAPTCHA_SECRET=

# Worker / polling
FETCH_RETRY_MAX=3
FETCH_RETRY_BASE=1.5
WORKER_POLL_SECONDS=2
STALE_JOB_MINUTES=30
STATUS_POLL_SECONDS=2
LIST_POLL_SECONDS=5

# Export
EXPORT_MAX_ROWS=5000

# Optional debug toggle
DISABLE_LOCAL_WHISPER=0
```

---

## 11. Instagram Cookies Setup
Cookies are used by yt-dlp fallback paths and can significantly improve reliability for Instagram content access.

### Why this matters
- Instagram frequently throttles or blocks unauthenticated scraping patterns.
- A fresh cookie jar can help yt-dlp access content metadata and media URLs.

### Steps
1. Log in to Instagram in Chrome (or another Chromium browser).
2. Install extension: **Get cookies.txt LOCALLY**.
3. Export cookies while on `instagram.com`.
4. Save the file as `instagram_cookies.txt` in project root.
5. Set `IG_COOKIES_FILE=./instagram_cookies.txt` in `.env`.

### Refresh frequency
- Refresh every 2-3 weeks, or sooner if requests start failing.

> ?? Warning: Never commit `instagram_cookies.txt` to Git. It contains active session credentials.

---

## 12. API Keys Setup
### OpenAI (summary generation)
1. Create/sign in to your OpenAI account: https://platform.openai.com/
2. Open API keys page: https://platform.openai.com/api-keys
3. Create a key and set `OPENAI_API_KEY` in `.env`.
4. Optionally choose a model using `OPENAI_SUMMARY_MODEL` (default `gpt-4o-mini`).

### Azure OpenAI (optional alternative)
1. Create Azure OpenAI resource in Azure Portal.
2. Create a model deployment.
3. Set:
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_API_KEY`
   - `AZURE_OPENAI_API_VERSION`
   - `AZURE_OPENAI_DEPLOYMENT`

### RapidAPI (primary metadata fetcher)
1. Sign up at https://rapidapi.com/
2. Subscribe to an Instagram reels/profile scraper API.
3. Copy your key to `RAPIDAPI_KEY`.

### Apify (third-layer fallback)
1. Sign up at https://apify.com/
2. Open account integrations and copy API token:
   - https://console.apify.com/account/integrations
3. Set `APIFY_TOKEN` in `.env`.

> ?? Tip: Configure at least two fetch layers for better resilience when one provider is rate-limited.

---

## 13. How It Works (Plain English)
When a user signs in, they land on one dashboard page. At the top, they paste an Instagram username or profile link and click Search. The app fetches only profile details, reel metadata, and thumbnail references first, so the page can load quickly instead of forcing full transcription immediately.

After metadata appears, the user decides what to process. They can generate insights for one reel or all reels in that profile. Each generation request starts a background job, and the page receives real-time updates so users can see what the system is doing without refreshing.

For each reel, the app checks if audio already exists locally. If not, it downloads audio and thumbnail assets. Then it transcribes speech locally with Whisper and generates a title plus a detailed summary with OpenAI (or Azure OpenAI if configured). If AI keys are missing, the app falls back to local summarization so work can still continue.

Every result is saved in SQLite and tied to the signed-in user. That means users only see their own processed records. Once complete, they can search/sort the reel list, read transcripts and detailed summaries, play local audio, and export profile data as CSV or JSON.

---

## 14. API Endpoints Reference
| Method | Route | Description | Response |
|---|---|---|---|
| GET | `/` | Entry route, redirects to login or dashboard | Redirect |
| GET | `/dashboard` | Main workspace page | HTML |
| POST | `/dashboard/search` | Search username/URL and load metadata | Redirect |
| POST | `/analyze` | Legacy alias to dashboard search | Redirect |
| GET | `/results/<path:username>` | Legacy route, redirects to dashboard profile | Redirect |
| GET | `/auth/login` | Login page | HTML |
| POST | `/auth/login` | Authenticate user | Redirect |
| GET | `/auth/signup` | Signup page | HTML |
| POST | `/auth/signup` | Register user | Redirect |
| POST | `/auth/logout` | Logout current session | Redirect |
| GET | `/proxy-image` | Proxy external thumbnail image URL | Image response |
| POST | `/api/reels/<int:reel_id>/generate` | Queue single reel processing job | JSON |
| POST | `/api/profiles/<int:profile_id>/generate-all` | Queue batch processing job | JSON |
| GET | `/api/stream/<int:job_id>` | SSE stream for job events/progress | `text/event-stream` |
| GET | `/thumbnails/<username>/<path:filename>` | Serve local thumbnail with recovery fallback | Image or Redirect |
| GET | `/audio/<username>/<path:filename>` | Serve local audio file | Audio stream |
| GET | `/export/profile/<int:profile_id>?format=csv` | Export profile reels as CSV | CSV download |
| GET | `/export/profile/<int:profile_id>?format=json` | Export profile reels as JSON | JSON download |

---

## 15. Whisper Model Selection Guide
| Model | Speed | Accuracy | RAM Required | Recommended For |
|---|---|---|---|---|
| `tiny` | Fastest | Low | ~1 GB | Quick functional tests |
| `base` | Fast | Good | ~1 GB | Default for most users |
| `small` | Medium | Better | ~2 GB | Better quality with moderate runtime |
| `medium` | Slow | High | ~5 GB | High-accuracy local runs |
| `large` | Slowest | Best | ~10 GB+ | GPU-capable systems |

Set in `.env`:
```bash
WHISPER_MODEL=base
```

---

## 16. Known Limitations
- Works only with public Instagram content that current fetch providers can access.
- Instagram/provider rate limiting can still impact metadata retrieval speed and success.
- Processing time scales with reel count and audio duration.
- SQLite is convenient for local/single-node usage but can lock under heavy concurrent writes.
- Whisper quality can degrade with heavy music, overlapping speakers, or low-quality audio.
- Cookies must be refreshed periodically if yt-dlp starts failing.
- Legacy templates/routes still exist in repo but active UX is auth + dashboard workflow.

---

## 17. Troubleshooting
| Error / Symptom | Likely Cause | Exact Fix |
|---|---|---|
| `database is locked` | Concurrent SQLite writes | Keep one local app instance, ensure WAL mode enabled, retry request, reduce concurrent jobs |
| `ffprobe and ffmpeg not found` | ffmpeg not installed or not in PATH | Install ffmpeg/ffprobe and set `FFMPEG_LOCATION` to ffmpeg folder if needed |
| `Failed to download reel audio` | yt-dlp fetch failure, missing cookies, or blocked media URL | Refresh `instagram_cookies.txt`, verify reel URL still exists, retry with another fetch layer |
| Audio route returns 404 | `audio_path` mismatch or file moved | Ensure file exists under `downloads/<username>/audio/`, regenerate reel to repair path |
| Thumbnails not rendering | External Instagram CDN hotlink restrictions | Use built-in `/proxy-image` and verify `thumbnail_url` is present |
| `Client.__init__() got an unexpected keyword argument 'proxies'` | Incompatible client init pattern with current `httpx/openai` stack | Remove unsupported `proxies` argument and use default client transport settings |
| Reel shows `No spoken content detected` | No transcribable speech in audio | Expected behavior; summary will reflect no speech |
| OpenAI summary fails silently | Missing/invalid `OPENAI_API_KEY` or Azure config | Fix key values in `.env`; fallback summarizer should still produce minimal output |
| SSE stops updating | EventSource disconnected/network interruption | Refresh page and reconnect stream; check Flask logs for job status |
| Profile search returns nothing | Provider blocked/throttled | Configure multiple fetch layers (`RAPIDAPI_KEY`, cookies, `APIFY_TOKEN`) |

> ?? Tip: If one provider fails often, keep at least two providers configured so fallback can take over automatically.

---

## 18. Contributing
1. Fork the repository.
2. Create a feature branch:
```bash
git checkout -b feature/your-feature-name
```
3. Make focused changes with clear commit messages:
```bash
git commit -m "feat: add xyz improvement"
```
4. Run local verification:
```bash
python -m compileall app
```
5. Push branch and open a Pull Request.

### Commit conventions
- `feat:` new features
- `fix:` bug fixes
- `refactor:` internal restructuring without behavior change
- `docs:` documentation updates
- `chore:` maintenance and tooling

### PR expectations
- Explain user impact and technical approach.
- Include screenshots/GIFs for UI changes.
- Mention any new environment variables or migration impact.

---

## 19. License
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

---

## 20. Acknowledgements
- Flask: https://flask.palletsprojects.com/
- SQLAlchemy: https://www.sqlalchemy.org/
- OpenAI API: https://platform.openai.com/
- OpenAI Whisper: https://github.com/openai/whisper
- yt-dlp: https://github.com/yt-dlp/yt-dlp
- Apify Client: https://docs.apify.com/api/client/python
- RapidAPI marketplace: https://rapidapi.com/
- sumy: https://github.com/miso-belica/sumy
- nltk: https://www.nltk.org/

