
# 📽️ PDF-to-Narration Video Generator — Implementation Plan


## 🏗️ High-Level Architecture

```
User (Browser)
    │
    ▼
Streamlit Frontend
    │
    ├──► Supabase Auth (Google OAuth)
    ├──► Supabase DB (PostgreSQL + pgvector)
    ├──► Supabase Storage (PDFs, Audio, Video)
    └──► Python Backend Services
              ├──► Gemini API (Narration)
              ├──► Deepgram API (TTS Audio)
              └──► FFmpeg (Video Assembly)
```

---

## 📦 Module Breakdown

| Module | Responsibility |
|---|---|
| `auth_service` | Google login via Supabase, session management |
| `key_service` | Encrypt/decrypt user API keys |
| `pdf_service` | Upload, split pages, extract text, convert to images |
| `narration_service` | Call Gemini API to generate narration per page |
| `audio_service` | Call Deepgram API to generate audio per page |
| `memory_service` | Manage pgvector embeddings and context retrieval |
| `video_service` | Combine page images + audio using FFmpeg |
| `storage_service` | Handle all Supabase Storage operations |
| `job_service` | Manage async background processing pipeline |

---

## 🗄️ Database Schema

### `users`
```
id (uuid, PK)
email
created_at
```

### `api_keys`
```
id (uuid, PK)
user_id (FK → users)
gemini_key_encrypted (text)
deepgram_key_encrypted (text)
iv (text)  ← encryption initialization vector
updated_at
```

### `projects`
```
id (uuid, PK)
user_id (FK → users)
title
pdf_path (Supabase Storage path)
status (enum: pending | processing | done | failed)
video_url
created_at
```

### `page_memories`
```
id (uuid, PK)
project_id (FK → projects)
page_number (int)
summary (text)
key_points (text[])
embedding (vector(768))  ← pgvector
created_at
```

### `processing_logs`
```
id (uuid, PK)
project_id (FK → projects)
page_number (int)
stage (text)  ← e.g. "narration", "audio", "video"
status (text)
error_message (text)
created_at
```

---

## 🔐 API Key Encryption Strategy

- Use **AES-256-GCM** symmetric encryption (via Python `cryptography` library)
- Encryption key is derived from a **server-side secret** (stored in `.env`, never in DB)
- Each user's key pair gets a unique **IV (initialization vector)** stored in `api_keys.iv`
- Flow:
  1. User submits API keys via Streamlit form
  2. Backend encrypts keys server-side before saving to DB
  3. Keys are decrypted **only at runtime**, in memory, per request
  4. Frontend **never** sees raw keys after initial submission

---

## 🔄 Core Processing Pipeline (Step-by-Step)

```
1. User uploads PDF
        │
        ▼
2. pdf_service → Split into pages → Extract text per page
                                 → Convert pages to images (PNG)
        │
        ▼
3. For each page (sequential):
   │
   ├─► memory_service → Query pgvector for top-3 relevant past summaries
   │
   ├─► narration_service → Send (page text + retrieved context) to Gemini
   │                      → Receive narration script
   │
   ├─► audio_service → Send narration to Deepgram → Get .mp3 audio file
   │
   └─► memory_service → Generate embedding for this page's summary
                      → Store summary + embedding in page_memories
        │
        ▼
4. All pages done → video_service
        │
        ├─► Pair each page image with its audio segment
        ├─► Use FFmpeg to create per-page video clips
        └─► Concatenate all clips into final .mp4
        │
        ▼
5. storage_service → Upload final .mp4 to Supabase Storage
        │
        ▼
6. Update projects.video_url + status = "done"
        │
        ▼
7. Streamlit dashboard → Display video to user
```

---

## 🧬 Vector Memory Strategy (pgvector)

- **Embedding model:** Use Gemini's embedding endpoint (`models/embedding-001`)
- **Per page flow:**
  1. After narration is generated, summarize the page content
  2. Generate embedding for the summary
  3. Store in `page_memories` table
- **Before each page's narration:**
  1. Generate a query embedding from the current page's raw text
  2. Run a cosine similarity search against `page_memories` for the same `project_id`
  3. Retrieve top-3 most relevant past page summaries
  4. Inject into Gemini prompt as context

---

## ⚙️ Async Job Handling

- Streamlit doesn't natively support background jobs — use **Python `threading`** for MVP
- On PDF upload, spawn a background thread that runs the full pipeline
- Store progress in the `projects.status` and `processing_logs` table
- Streamlit frontend polls the DB every few seconds and updates the UI status
- For future scale: replace threading with **Celery + Redis** task queue

---

## 📁 File Handling Strategy

| File Type | Where Stored | When Deleted |
|---|---|---|
| Uploaded PDF | Supabase Storage | Never (user owns it) |
| Page images (PNG) | Local `/tmp` during processing | After video is built |
| Audio segments (MP3) | Local `/tmp` during processing | After video is built |
| Page video clips | Local `/tmp` during processing | After final merge |
| Final video (MP4) | Supabase Storage | Never (user owns it) |

- Use Python `tempfile` module to manage all intermediate `/tmp` files
- Clean up temp files in a `finally` block to avoid disk bloat

---

## 🚦 API Rate Limit Handling

| API | Strategy |
|---|---|
| Gemini | Add `time.sleep(1)` between page calls; retry with exponential backoff on 429 |
| Deepgram | Sequential audio requests; retry on failure with delay |

- Wrap all API calls in a `retry_with_backoff(fn, max_retries=3)` utility
- Log every retry attempt to `processing_logs`

---

## ❌ Error Handling Strategy

- Each pipeline stage is wrapped in try/except
- On failure: log error to `processing_logs`, set project status to `"failed"`
- User sees friendly error message in dashboard with which page/stage failed
- Partial failures are recoverable — system tracks which pages are done, allowing resume logic in v2
- Never expose raw API errors or stack traces to the frontend

---

## 🎨 Streamlit UI Flow

```
Page 1: Login Screen
    └── Google OAuth button (Supabase)

Page 2: API Key Setup (shown once after first login)
    └── Gemini Key input + Deepgram Key input

Page 3: Dashboard
    ├── Upload PDF
    ├── Processing Status (live polling)
    └── Video player (once done)
```

---

## 🚀 Deployment Plan

### MVP (Local / Single Server)
- Run Streamlit app on a **VPS (e.g. Hetzner, DigitalOcean)**
- Use `tmux` or `screen` to keep the process alive
- Use `nginx` as a reverse proxy to expose the Streamlit port
- Use **Supabase cloud** for DB, Auth, and Storage (no self-hosting needed)
- FFmpeg installed directly on the server via `apt`
- Store `.env` with all secrets on the server (not in code)

### Scalability Upgrade Path
- Move processing pipeline to a **separate FastAPI backend** service
- Streamlit calls FastAPI via REST — clean frontend/backend separation
- Add **Celery + Redis** for proper async task queue
- Add **per-user rate limits** and **job queues** at the API layer
- Use **Supabase Edge Functions** for lightweight webhook handlers

---

## 📝 `notes.md` Structure

```markdown
# Project Notes — PDF-to-Narration Video Generator

## ✅ Progress Tracker
- [ ] Supabase Auth (Google OAuth)
- [ ] API Key encryption + storage
- [ ] PDF upload + page splitting
- [ ] Gemini narration generation
- [ ] Deepgram TTS audio generation
- [ ] pgvector memory system
- [ ] FFmpeg video assembly
- [ ] Supabase video storage
- [ ] Streamlit dashboard + video player

## 🔧 Features Implemented
(Add entries as features are completed)

## 🔄 Improvements Made
(Track refactors, optimizations, bug fixes)

## 🏆 Achievements
- Built a full end-to-end AI-powered PDF narration pipeline
- Implemented AES-256 encrypted API key storage per user
- Integrated vector memory for context-aware narration using pgvector
- Designed a modular Python backend with clean service separation
- Deployed a production-ready Streamlit SaaS application
```

---

## 🧭 Suggested Implementation Order

1. Set up Supabase project (DB, Auth, Storage, pgvector extension)
2. Build `auth_service` — Google login working in Streamlit
3. Build `key_service` — encrypt/decrypt + store API keys
4. Build `pdf_service` — upload, split, extract text + images
5. Build `memory_service` — pgvector setup, store + retrieve embeddings
6. Build `narration_service` — Gemini integration with context injection
7. Build `audio_service` — Deepgram TTS integration
8. Build `video_service` — FFmpeg assembly pipeline
9. Build `storage_service` — upload final video to Supabase
10. Wire everything into `job_service` with async threading
11. Build full Streamlit UI with status polling + video player
12. Deploy to VPS with nginx + environment config