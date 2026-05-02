import sys
import os
import time

# Ensure the root directory is in the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from services.auth_service import login_with_google, handle_oauth_callback, get_current_user, logout
from services.key_service import save_api_keys, has_api_keys
from services.pdf_service import upload_pdf, download_pdf, split_pdf_to_pages
from services.narration_service import generate_narration
from services.tts_service import generate_audio
from services.video_service import generate_video
from utils.logger import get_logger

logger = get_logger(__name__)

def get_all_narrations():
    """Returns an ordered list of all structured narration objects."""
    if "narrations" not in st.session_state:
        return []
    return sorted(st.session_state["narrations"], key=lambda x: x["page"])

st.set_page_config(page_title="NarrateIt", layout="wide")

# ─────────────────────────────────────────────
# DESIGN SYSTEM — Ultra Compact Tool UI
# ─────────────────────────────────────────────
def inject_custom_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

        /* ── Reset & Global Text Overlap Fix ── */
        * { 
            font-family: 'Inter', sans-serif !important; 
            line-height: 1.5 !important; 
            word-wrap: break-word !important; 
        }

        .stApp { background-color: #0B0F19; }
        [data-testid="stAppViewContainer"] { background-color: #0B0F19; }
        
        /* ── Google Button ── */
        .google-btn-wrapper [data-testid="baseButton-secondary"] {
            background-color: #FFFFFF !important;
            color: #3C4043 !important;
            border: 1px solid #DADCE0 !important;
            border-radius: 4px !important;
            font-weight: 500 !important;
            padding-left: 36px !important;
            position: relative;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }
        .google-btn-wrapper [data-testid="baseButton-secondary"]::before {
            content: "";
            position: absolute;
            left: 12px;
            width: 18px;
            height: 18px;
            background-image: url('https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg');
            background-size: cover;
            background-repeat: no-repeat;
        }
        .google-btn-wrapper [data-testid="baseButton-secondary"]:hover {
            background-color: #F8F9FA !important;
        }
        [data-testid="stHeader"] { background-color: #0B0F19; border-bottom: 1px solid #1E293B; }

        /* ── Sidebar ── */
        [data-testid="stSidebar"] { background-color: #111827; border-right: 1px solid #1E293B; }
        [data-testid="stSidebar"] .stMarkdown p,
        [data-testid="stSidebar"] .stMarkdown span { color: #94A3B8 !important; }

        /* ── Typography — compact, no overlap ── */
        h1, h2, h3, h4, h5, h6 {
            color: #F1F5F9 !important;
            font-weight: 700 !important;
            line-height: 1.4 !important;
            overflow-wrap: break-word;
        }
        p, span, label, div, li {
            color: #94A3B8;
            line-height: 1.5;
            overflow-wrap: break-word;
        }

        /* ── Containers — thin ── */
        [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #111827 !important;
            border: 1px solid #1E293B !important;
            border-radius: 8px !important;
            padding: 4px 8px;
        }

        /* ── Expander — compact ── */
        [data-testid="stExpander"] {
            background-color: #111827;
            border: 1px solid #1E293B !important;
            border-radius: 8px !important;
        }
        [data-testid="stExpander"] summary span p {
            color: #F1F5F9 !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
        }

        /* ── Buttons — small, flat ── */
        .stButton > button {
            background-color: #1E293B !important;
            color: #CBD5E1 !important;
            border: 1px solid #334155 !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
            font-size: 0.8rem !important;
            padding: 4px 12px !important;
            min-height: 0 !important;
            line-height: 1.4 !important;
            transition: background 0.1s ease !important;
            box-shadow: none !important;
        }
        .stButton > button:hover {
            background-color: #334155 !important;
            transform: none !important;
            box-shadow: none !important;
        }
        .stButton > button p {
            color: #CBD5E1 !important;
            font-weight: 600 !important;
            font-size: 0.8rem !important;
        }

        /* ── Active page pill ── */
        .stButton > button[kind="primary"] {
            background-color: #22C55E !important;
            color: #0B0F19 !important;
            border-color: #16A34A !important;
        }
        .stButton > button[kind="primary"] p {
            color: #0B0F19 !important;
        }

        /* ── Download button ── */
        .stDownloadButton > button {
            background-color: #3B82F6 !important;
            color: white !important;
            border: 1px solid #2563EB !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
            font-size: 0.8rem !important;
            box-shadow: none !important;
        }
        .stDownloadButton > button p { color: white !important; }

        /* ── Image — capped ── */
        [data-testid="stImage"] img {
            border-radius: 6px;
            border: 1px solid #1E293B;
            max-height: 300px;
            object-fit: contain;
            background-color: #0B0F19;
        }

        /* ── Audio — compact ── */
        [data-testid="stAudio"] {
            background-color: #1E293B;
            border-radius: 6px;
            padding: 4px;
            border: 1px solid #334155;
        }

        /* ── File Uploader Clean ── */
        [data-testid="stFileUploader"] {
            background-color: #111827;
            border: 1px solid #1E293B;
            border-radius: 8px;
            padding: 12px;
        }

        /* ── Select & Slider ── */
        .stSelectbox label, .stSlider label {
            color: #CBD5E1 !important;
            font-weight: 600 !important;
            font-size: 0.8rem !important;
        }

        /* ── Landing ── */
        .landing-hero {
            text-align: center;
            padding: 40px 20px 24px 20px;
        }
        .landing-hero h1 {
            font-size: 2.4rem !important;
            font-weight: 900 !important;
            color: #F1F5F9 !important;
            line-height: 1.3 !important;
            margin-bottom: 12px;
            max-width: 700px;
            margin-left: auto;
            margin-right: auto;
        }
        .landing-hero .accent { color: #22C55E !important; }
        .landing-hero p {
            font-size: 1rem;
            color: #94A3B8 !important;
            max-width: 560px;
            margin: 0 auto 24px auto;
            line-height: 1.5;
        }

        .feature-card {
            background-color: #111827;
            border: 1px solid #1E293B;
            border-radius: 8px;
            padding: 20px 16px;
            text-align: center;
        }
        .feature-card .icon { font-size: 1.6rem; margin-bottom: 8px; }
        .feature-card h3 {
            font-size: 0.9rem !important;
            font-weight: 700 !important;
            color: #F1F5F9 !important;
            margin-bottom: 4px;
        }
        .feature-card p { font-size: 0.8rem; color: #64748B !important; margin: 0; }

        .step-bar {
            background-color: #111827;
            border: 1px solid #1E293B;
            border-radius: 8px;
            padding: 16px 12px;
            text-align: center;
        }
        .step-bar .step-num {
            display: inline-block;
            width: 24px; height: 24px;
            line-height: 24px;
            background-color: #22C55E;
            color: #0B0F19;
            font-weight: 800;
            border-radius: 6px;
            font-size: 0.75rem;
            margin-bottom: 6px;
        }
        .step-bar p { color: #CBD5E1 !important; font-weight: 600; font-size: 0.78rem; margin: 0; }

        /* ── Toolbar ── */
        .toolbar-label {
            font-size: 0.75rem;
            color: #64748B !important;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 2px;
        }

        /* ── Page pills strip ── */
        .page-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            padding: 8px 0;
        }

        /* ── Status dot ── */
        .dot-ok { color: #22C55E !important; font-size: 0.7rem; }
        .dot-pending { color: #475569 !important; font-size: 0.7rem; }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# LANDING PAGE
# ─────────────────────────────────────────────
def render_landing_page():
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown("""
        <div class="landing-hero">
            <h1>Turn PDFs into <span class="accent">Narrated Videos</span> in Seconds</h1>
            <p>Upload any PDF — get AI narration, audio, and a polished video automatically.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="google-btn-wrapper">', unsafe_allow_html=True)
        if st.button("Continue with Google", use_container_width=True):
            login_with_google()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    f1, f2, f3 = st.columns(3)
    with f1:
        st.markdown('<div class="feature-card"><div class="icon">📄</div><h3>Upload PDFs</h3><p>Documents, slides, and comics</p></div>', unsafe_allow_html=True)
    with f2:
        st.markdown('<div class="feature-card"><div class="icon">🧠</div><h3>Smart Narration</h3><p>AI adapts tone automatically</p></div>', unsafe_allow_html=True)
    with f3:
        st.markdown('<div class="feature-card"><div class="icon">🎬</div><h3>Audio + Video</h3><p>Voice narration and final video</p></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<p class='toolbar-label' style='text-align:center;'>How It Works</p>", unsafe_allow_html=True)

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown('<div class="step-bar"><div class="step-num">1</div><p>Upload PDF</p></div>', unsafe_allow_html=True)
    with s2:
        st.markdown('<div class="step-bar"><div class="step-num">2</div><p>Generate Narration</p></div>', unsafe_allow_html=True)
    with s3:
        st.markdown('<div class="step-bar"><div class="step-num">3</div><p>Generate Audio</p></div>', unsafe_allow_html=True)
    with s4:
        st.markdown('<div class="step-bar"><div class="step-num">4</div><p>Export Video</p></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# API KEYS SETTINGS
# ─────────────────────────────────────────────
def render_api_keys_settings(user_id):
    st.markdown("<p class='toolbar-label'>Settings / API Keys</p>", unsafe_allow_html=True)

    with st.container(border=True):
        keys_exist = has_api_keys(user_id)
        if keys_exist:
            st.success("API Keys configured.", icon="✅")
        else:
            st.warning("Configure your API keys to use the app.")

        with st.form("api_keys_form"):
            gemini_key = st.text_input("Gemini API Key", type="password")
            deepgram_key = st.text_input("Deepgram API Key", type="password")
            submit = st.form_submit_button("Save Keys")

            if submit:
                if gemini_key and deepgram_key:
                    try:
                        logger.info("Saving new API keys from UI")
                        save_api_keys(user_id, gemini_key, deepgram_key)
                        st.success("Saved!")
                    except Exception as e:
                        logger.error("Failed to save API keys from UI", exc_info=True)
                        st.error("Failed to save keys.")
                else:
                    st.error("Provide both keys.")


# ─────────────────────────────────────────────
# PAGE PREVIEW DIALOG
# ─────────────────────────────────────────────
@st.dialog("Page Detail")
def show_page_popup(pn, pages, narrations, user_id, selected_voice, selected_speed):
    sel_page = next((p for p in pages if p['page_number'] == pn), None)
    if not sel_page:
        return
        
    st.image(sel_page['image_path'], use_container_width=True)
    
    page_nar = next((n for n in narrations if n["page"] == pn), None)
    has_audio = pn in st.session_state.get("audio_map", {})

    if page_nar:
        st.text_area("Narration Script", page_nar["text"], height=140, disabled=True, key=f"popup_script_{pn}")
        if has_audio:
            st.audio(st.session_state["audio_map"][pn])
        else:
            if st.button("Generate Audio", key=f"popup_pa_{pn}", use_container_width=True):
                with st.spinner("Generating..."):
                    try:
                        ap = generate_audio(text=page_nar["text"], user_id=user_id, page=pn, voice_model=selected_voice, speed=selected_speed)
                        st.session_state["audio_map"][pn] = ap
                        st.rerun()
                    except Exception as e:
                        logger.error("Audio gen failed", exc_info=True)
                        st.error(str(e))
    else:
        if st.button("Generate Narration", key=f"popup_pn_{pn}", use_container_width=True):
            with st.spinner("Generating..."):
                try:
                    result = generate_narration(page_text=sel_page['text'], context=None, user_id=user_id, image_path=sel_page['image_path'])
                    st.session_state["narrations"] = [n for n in st.session_state.get("narrations", []) if n["page"] != pn]
                    st.session_state["narrations"].append({"page": pn, "text": result, "image_path": sel_page['image_path']})
                    st.rerun()
                except Exception as e:
                    logger.error("Narration gen failed", exc_info=True)
                    st.error(str(e))

# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
def render_dashboard(user_id):
    if not has_api_keys(user_id):
        st.warning("Configure API keys in Settings first.")
        return

    # ── Row 1: Upload + Settings toolbar ──
    t1, t2, t3 = st.columns([2, 1, 1])
    with t1:
        uploaded_file = st.file_uploader("Upload PDF Document", type=["pdf"])
    with t2:
        selected_voice = st.selectbox("Voice", ["aura-asteria-en", "aura-luna-en", "aura-orion-en", "aura-2-amalthea-en"], label_visibility="collapsed")
    with t3:
        selected_speed = st.slider("Speed", 0.75, 1.25, 1.0, 0.05, label_visibility="collapsed")

    # Handle file upload
    if uploaded_file is not None:
        if st.session_state.get("current_pdf") != uploaded_file.name:
            st.session_state["pages"] = []
            st.session_state["narrations"] = []
            st.session_state["audio_map"] = {}
            st.session_state["video_file"] = None
            st.session_state["current_pdf"] = uploaded_file.name
            st.rerun()

        if not st.session_state["pages"]:
            if st.button("Process PDF"):
                logger.info(f"User {user_id} triggered PDF processing")
                with st.spinner("Processing..."):
                    try:
                        file_bytes = uploaded_file.getvalue()
                        storage_path = upload_pdf(file_bytes, user_id)
                        local_pdf_path = download_pdf(storage_path)
                        pages = split_pdf_to_pages(local_pdf_path)
                        st.session_state["pages"] = pages
                        logger.info("Successfully processed PDF and stored pages in session state")
                        if os.path.exists(local_pdf_path):
                            os.remove(local_pdf_path)
                        st.rerun()
                    except Exception as e:
                        logger.error("Error occurred during PDF processing flow", exc_info=True)
                        st.error(f"Error: {str(e)}")
            return
    else:
        st.markdown("<p style='text-align:center; color:#475569; font-size:0.85rem;'>Upload a PDF to get started.</p>", unsafe_allow_html=True)
        return

    if not st.session_state["pages"]:
        return

    pages = st.session_state["pages"]
    narrations = get_all_narrations()

    # ── Row 2: Action toolbar ──
    a1, a2, a3 = st.columns(3)
    with a1:
        if st.button("Generate All Narrations", use_container_width=True):
            bar = st.progress(0)
            txt = st.empty()
            for i, page in enumerate(pages):
                pn = page['page_number']
                if any(n["page"] == pn for n in st.session_state["narrations"]):
                    bar.progress((i + 1) / len(pages))
                    continue
                txt.text(f"Narrating page {pn}...")
                try:
                    result = generate_narration(page_text=page['text'], context=None, user_id=user_id, image_path=page['image_path'])
                    st.session_state["narrations"] = [n for n in st.session_state["narrations"] if n["page"] != pn]
                    st.session_state["narrations"].append({"page": pn, "text": result, "image_path": page['image_path']})
                except Exception as e:
                    logger.error(f"Narration failed for page {pn}", exc_info=True)
                    st.error(f"Page {pn}: {str(e)}")
                bar.progress((i + 1) / len(pages))
                time.sleep(1)
            txt.text("Done.")
            st.rerun()

    with a2:
        if st.button("Generate All Audio", use_container_width=True):
            nars = get_all_narrations()
            if not nars:
                st.warning("Generate narrations first.")
            else:
                bar = st.progress(0)
                txt = st.empty()
                for i, n_obj in enumerate(nars):
                    pn = n_obj["page"]
                    if pn in st.session_state["audio_map"]:
                        bar.progress((i + 1) / len(nars))
                        continue
                    txt.text(f"Audio for page {pn}...")
                    try:
                        audio_path = generate_audio(text=n_obj["text"], user_id=user_id, page=pn, voice_model=selected_voice, speed=selected_speed)
                        st.session_state["audio_map"][pn] = audio_path
                    except Exception as e:
                        logger.error(f"Audio failed for page {pn}", exc_info=True)
                        st.error(f"Page {pn}: {str(e)}")
                    bar.progress((i + 1) / len(nars))
                    time.sleep(1)
                txt.text("Done.")
                st.rerun()

    with a3:
        if st.button("Generate Video", use_container_width=True):
            nars = get_all_narrations()
            if not nars or len(nars) != len(pages):
                st.warning("Generate all narrations first.")
            elif any(n["page"] not in st.session_state["audio_map"] for n in nars):
                st.warning("Generate all audio first.")
            else:
                with st.spinner("Rendering video..."):
                    try:
                        video_nars = []
                        for n in nars:
                            nc = dict(n)
                            nc["audio_path"] = st.session_state["audio_map"].get(n["page"])
                            video_nars.append(nc)
                        video_path = generate_video(video_nars, user_id)
                        st.session_state["video_file"] = video_path
                        st.rerun()
                    except Exception as e:
                        logger.error("Video generation failed", exc_info=True)
                        st.error(f"Error: {str(e)}")

    # ── Row 3: Horizontal page strip ──

    st.markdown("<hr style='margin:8px 0; border-color:#1E293B;'>", unsafe_allow_html=True)
    
    st.markdown('<div class="page-row-marker"></div>', unsafe_allow_html=True)
    
    css_rules = []
    css_rules.append("""
        .page-row-marker + div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            overflow-x: auto !important;
            padding-bottom: 12px;
            gap: 4px !important;
            justify-content: flex-start !important;
        }
        .page-row-marker + div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            min-width: 44px !important;
            max-width: 44px !important;
            flex: 0 0 44px !important;
            width: 44px !important;
        }
        .page-row-marker + div[data-testid="stHorizontalBlock"] button {
            height: 36px !important;
            padding: 0 !important;
            display: flex;
            justify-content: center;
            align-items: center;
            border-radius: 6px !important;
        }
    """)
    
    cols = st.columns(len(pages))
    for idx, page in enumerate(pages):
        pn = page['page_number']
        has_nar = any(n["page"] == pn for n in narrations)
        has_aud = pn in st.session_state["audio_map"]
        
        bg_color = "#1E293B"
        text_color = "#94A3B8"
        border_color = "#334155"
        
        if has_aud:
            bg_color = "#059669"
            text_color = "#FFFFFF"
            border_color = "#047857"
        elif has_nar:
            bg_color = "#D97706"
            text_color = "#FFFFFF"
            border_color = "#B45309"
            
        css_rules.append(f".page-row-marker + div > div:nth-child({idx+1}) button {{ background-color: {bg_color} !important; color: {text_color} !important; border: 2px solid {border_color} !important; }}")
        css_rules.append(f".page-row-marker + div > div:nth-child({idx+1}) button p {{ color: {text_color} !important; font-weight: 700 !important; }}")
        
        with cols[idx]:
            if st.button(f"P{pn}", key=f"pill_{pn}"):
                show_page_popup(pn, pages, narrations, user_id, selected_voice, selected_speed)

    st.markdown(f"<style>{''.join(css_rules)}</style>", unsafe_allow_html=True)



    # ── Row 5: Final video (compact) ──
    if st.session_state.get("video_file"):
        st.markdown("<hr style='margin:12px 0; border-color:#1E293B;'>", unsafe_allow_html=True)
        _, vid_center, _ = st.columns([1, 2, 1])
        with vid_center:
            st.markdown("<p class='toolbar-label'>Final Output</p>", unsafe_allow_html=True)
            st.video(st.session_state["video_file"])
            try:
                with open(st.session_state["video_file"], "rb") as vf:
                    st.download_button("Download Video", data=vf, file_name="narration_video.mp4", mime="video/mp4", use_container_width=True)
            except Exception as e:
                logger.error("Video download failed", exc_info=True)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    for key, default in [("pages", []), ("narrations", []), ("audio_map", {}), ("video_file", None), ("selected_page", None), ("current_pdf", None)]:
        if key not in st.session_state:
            st.session_state[key] = default

    inject_custom_css()
    handle_oauth_callback()
    user = get_current_user()

    if user is None:
        render_landing_page()
    else:
        st.sidebar.markdown(f"**{user.email}**")
        st.sidebar.markdown("---")
        nav = st.sidebar.radio("Nav", ["Dashboard", "Settings"], label_visibility="collapsed")
        st.sidebar.markdown("---")
        if st.sidebar.button("Logout", use_container_width=True):
            logger.info(f"User {user.id} requested logout")
            logout()

        if nav == "Dashboard":
            render_dashboard(user.id)
        elif nav == "Settings":
            render_api_keys_settings(user.id)

if __name__ == "__main__":
    main()
