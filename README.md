

Start backend
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
Start frontend
cd frontend
python -m http.server 5500

# NarrateIt

**Turn PDFs into Narrated Videos in Seconds.**

NarrateIt is a SaaS productivity tool that converts any PDF document into a polished narrated video. Upload a PDF, get AI-generated narration scripts, studio-quality audio, and a final video — all from your browser.

---

## ✨ Features

- **PDF Processing** — Upload any PDF; pages are split into individual images with extracted text.
- **AI Narration** — Google Gemini generates professional narration scripts for each page.
- **Text-to-Speech** — Deepgram synthesizes human-like audio from narration scripts.
- **Video Rendering** — MoviePy composites page images and audio into a downloadable MP4 video.
- **Google OAuth** — Secure login via Supabase Auth with persistent sessions.
- **Encrypted API Keys** — User API keys are stored encrypted in Supabase using Fernet symmetric encryption.
- **Compact Dashboard** — Seat-selection style page selector, popup-based page details, and inline status indicators.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Auth | Supabase (Google OAuth) |
| LLM | Google Gemini |
| TTS | Deepgram Aura |
| Video | MoviePy + FFmpeg |
| PDF Parsing | PyMuPDF (fitz) |
| Encryption | cryptography (Fernet) |

---

## 📁 Project Structure

```
Narrate_It/
├── app/
│   └── main.py              # Streamlit UI — landing page, dashboard, popup dialogs
├── services/
│   ├── auth_service.py       # Google OAuth login, session restore, logout
│   ├── key_service.py        # Encrypted API key storage & retrieval
│   ├── pdf_service.py        # PDF upload, download, page splitting
│   ├── narration_service.py  # Gemini-powered narration generation
│   ├── tts_service.py        # Deepgram text-to-speech
│   ├── video_service.py      # MoviePy video composition
│   └── supabase_client.py    # Supabase client singleton
├── utils/
│   ├── config.py             # Environment variable loader
│   ├── crypto.py             # Fernet encrypt/decrypt helpers
│   └── logger.py             # Structured logging setup
├── .env.example              # Required environment variables
├── requirements.txt          # Python dependencies
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **FFmpeg** — must be installed and available in your system PATH
- **ImageMagick** — required by MoviePy for video rendering
- A **Supabase** project with Google OAuth configured
- A **Google Gemini** API key
- A **Deepgram** API key

### 1. Clone the Repository

```bash
git clone https://github.com/devnickverma/Narrate_It.git
cd Narrate_It
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
ENCRYPTION_KEY=your-fernet-key
```

> **Generate a Fernet key:**
> ```python
> from cryptography.fernet import Fernet
> print(Fernet.generate_key().decode())
> ```

### 4. Run the App

```bash
streamlit run app/main.py
```

The app will be available at `http://localhost:8501`.

---

## 📖 Usage

1. **Login** — Click "Continue with Google" on the landing page.
2. **Configure Keys** — Go to **Settings** and enter your Gemini and Deepgram API keys.
3. **Upload PDF** — Use the upload bar on the dashboard.
4. **Process** — Click "Process PDF" to split pages.
5. **Generate** — Use the action toolbar:
   - `Generate All Narrations` → AI writes scripts for every page
   - `Generate All Audio` → Converts scripts to speech
   - `Generate Video` → Renders the final MP4
6. **Review** — Click any page button (P1, P2...) to open a popup with the image, script, and audio.
7. **Download** — The final video appears on the right side of the dashboard with a download button.

---

## 🎨 UI Overview

- **Landing Page** — Hero section with product messaging and Google login.
- **Dashboard** — Three-row layout:
  - **Row 1**: PDF upload + voice/speed settings
  - **Row 2**: Action buttons with live status indicators
  - **Row 3**: Page selector (left) + Video output (right)
- **Page Popup** — `@st.dialog` modal with split layout: image on left, narration + audio on right.

---

## ⚙️ Environment Variables

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (for admin operations) |
| `ENCRYPTION_KEY` | Fernet symmetric key for encrypting stored API keys |

---

## 📝 License

This project is for personal/educational use. See [LICENSE](LICENSE) for details.

---

## 🙋 Author

**Dev Nick Verma** — [@devnickverma](https://github.com/devnickverma)
