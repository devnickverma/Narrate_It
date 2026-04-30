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

st.set_page_config(page_title="PDF to Narration Video Generator", layout="wide")

def inject_custom_css():
    st.markdown("""
    <style>
        /* Dark Theme App Background */
        .stApp {
            background-color: #0f172a;
        }
        [data-testid="stAppViewContainer"] {
            background-color: #0f172a;
        }
        [data-testid="stHeader"] {
            background-color: rgba(15, 23, 42, 0.8);
        }
        
        /* Dark Sidebar */
        [data-testid="stSidebar"] {
            background-color: #1e293b;
            border-right: 1px solid #334155;
        }
        
        /* Gradient Hero Header */
        .hero-header {
            background: linear-gradient(135deg, #4f46e5, #9333ea);
            padding: 40px 20px;
            border-radius: 16px;
            text-align: center;
            margin-bottom: 25px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        }
        .hero-header h1 {
            color: #ffffff !important;
            margin: 0;
            font-size: 2.8rem;
            font-weight: 800;
        }
        .hero-header p {
            color: #e2e8f0 !important;
            margin-top: 10px;
            font-size: 1.2rem;
        }
        
        /* Card Styling for Bordered Containers */
        [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #1e293b;
            border-radius: 16px !important;
            border: 1px solid #334155 !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
            padding: 10px;
        }
        
        /* Buttons Styling */
        .stButton > button {
            background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            transition: all 0.2s ease-in-out !important;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
        }
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(139, 92, 246, 0.4) !important;
        }
        .stButton > button p {
            color: white !important;
        }
        
        /* Image Styling */
        [data-testid="stImage"] img {
            border-radius: 12px;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
            max-height: 550px;
            object-fit: contain;
            background-color: #0f172a;
        }
        
        /* Audio Player */
        [data-testid="stAudio"] {
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 10px;
            margin-top: 15px;
            border: 1px solid #334155;
        }
        
        /* Typography Overrides */
        h1, h2, h3, h4 {
            color: #f8fafc !important;
        }
        p, span, label, div {
            color: #cbd5e1;
        }
        
        /* Upload box */
        [data-testid="stFileUploader"] {
            background-color: rgba(255, 255, 255, 0.02);
            border-radius: 12px;
            padding: 10px;
        }
    </style>
    """, unsafe_allow_html=True)

def render_api_keys_settings(user_id):
    st.header("API Keys Settings")
    
    # Check if keys exist
    keys_exist = has_api_keys(user_id)
    if keys_exist:
        st.success("API Keys Configured ✅")
    else:
        st.warning("Please configure your API keys to use the app.")
        
    st.subheader("Update API Keys")
    with st.form("api_keys_form"):
        gemini_key = st.text_input("Gemini API Key", type="password")
        deepgram_key = st.text_input("Deepgram API Key", type="password")
        submit = st.form_submit_button("Save")
        
        if submit:
            if gemini_key and deepgram_key:
                try:
                    logger.info("Saving new API keys from UI")
                    save_api_keys(user_id, gemini_key, deepgram_key)
                    st.success("API Keys saved successfully!")
                except Exception as e:
                    logger.error("Failed to save API keys from UI", exc_info=True)
                    st.error("Failed to save keys. Please check logs.")
            else:
                st.error("Please provide both API keys.")

def render_dashboard(user_id):
    st.markdown("""
        <div class="hero-header">
            <h1>🎙️ PDF to Narration Studio</h1>
            <p>Turn PDFs into engaging voice narration instantly</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Check if we have API keys
    if not has_api_keys(user_id):
        st.warning("Please configure your API keys in the settings to use the generation features.")
        return
        
    # --- Upload Section ---
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("📁 Upload PDF")
        uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"], label_visibility="collapsed")
        
        if uploaded_file is not None:
            if st.button("Process PDF"):
                logger.info(f"User {user_id} triggered PDF processing")
                with st.spinner("Uploading and processing PDF..."):
                    try:
                        file_bytes = uploaded_file.getvalue()
                        storage_path = upload_pdf(file_bytes, user_id)
                        local_pdf_path = download_pdf(storage_path)
                        pages = split_pdf_to_pages(local_pdf_path)
                        if not st.session_state.get("pages"):
                            st.session_state["pages"] = pages
                        logger.info("Successfully processed PDF and stored pages in session state")
                        if os.path.exists(local_pdf_path):
                            os.remove(local_pdf_path)
                    except Exception as e:
                        logger.error("Error occurred during PDF processing flow", exc_info=True)
                        st.error("Error processing PDF. Please check the logs.")

    # --- Processing Section ---
    if st.session_state["pages"]:
        pages = st.session_state["pages"]
            
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.subheader("⚙️ Audio Settings")
            col_audio1, col_audio2 = st.columns(2)
            with col_audio1:
                selected_voice = st.selectbox("Voice Model", ["aura-asteria-en", "aura-luna-en", "aura-orion-en", "aura-2-amalthea-en"])
            with col_audio2:
                selected_speed = st.slider("Speech Speed", min_value=0.75, max_value=1.25, value=1.0, step=0.05)
                
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.subheader("⚡ Quick Actions")
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
            with col_btn1:
                if st.button("Generate Narration (All Pages)", use_container_width=True):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    for i, page in enumerate(pages):
                        page_num = page['page_number']
                        if any(n["page"] == page_num for n in st.session_state["narrations"]):
                            continue
                            
                        status_text.text(f"Generating narration for page {page_num}...")
                        try:
                            narration = generate_narration(
                                page_text=page['text'],
                                context=None,
                                user_id=user_id,
                                image_path=page['image_path']
                            )
                            # Remove existing and append to maintain structure safely
                            st.session_state["narrations"] = [n for n in st.session_state["narrations"] if n["page"] != page_num]
                            st.session_state["narrations"].append({
                                "page": page_num,
                                "text": narration,
                                "image_path": page['image_path']
                            })
                        except Exception as e:
                            logger.error(f"Failed to generate narration for page {page_num}", exc_info=True)
                            st.error(f"Failed to generate narration for page {page_num}.")
                        progress_bar.progress((i + 1) / len(pages))
                        time.sleep(1)
                    status_text.text("Completed all narration generation!")
                    st.rerun()
                    
            with col_btn2:
                if st.button("Generate Audio (All Pages)", use_container_width=True):
                    narrations = get_all_narrations()
                    if not narrations:
                        st.warning("Please generate narrations first.")
                    else:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        for i, narration_obj in enumerate(narrations):
                            page_num = narration_obj["page"]
                            if page_num in st.session_state["audio_map"]:
                                continue
                                
                            status_text.text(f"Generating audio for page {page_num}...")
                            try:
                                audio_path = generate_audio(
                                    text=narration_obj["text"],
                                    user_id=user_id,
                                    page=page_num,
                                    voice_model=selected_voice,
                                    speed=selected_speed
                                )
                                st.session_state["audio_map"][page_num] = audio_path
                            except Exception as e:
                                logger.error(f"Failed to generate audio for page {page_num}", exc_info=True)
                                st.error(f"Failed to generate audio for page {page_num}.")
                            progress_bar.progress((i + 1) / len(narrations))
                            time.sleep(1)
                        status_text.text("Completed audio generation for all pages!")
                        st.rerun()
                        
            with col_btn3:
                if st.button("Generate Final Video", use_container_width=True):
                    narrations = get_all_narrations()
                    if not narrations or len(narrations) != len(pages):
                        st.warning("Please generate narrations for all pages first.")
                    elif any(n["page"] not in st.session_state["audio_map"] for n in narrations):
                        st.warning("Please generate audio for all pages first.")
                    else:
                        with st.spinner("Generating final video... This may take a minute."):
                            try:
                                # Reconstruct narrations with audio path for video generation
                                video_narrations = []
                                for n in narrations:
                                    n_copy = dict(n)
                                    n_copy["audio_path"] = st.session_state["audio_map"].get(n["page"])
                                    video_narrations.append(n_copy)
                                    
                                video_path = generate_video(video_narrations, user_id)
                                st.session_state["video_path"] = video_path
                                st.rerun()
                            except Exception as e:
                                logger.error("Failed to generate final video", exc_info=True)
                                st.error("Failed to generate final video.")
                                
        # --- Final Video Section ---
        if st.session_state["video_path"]:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.subheader("🎬 Final Rendered Video")
                st.video(st.session_state["video_path"])
                
                try:
                    with open(st.session_state["video_path"], "rb") as video_file:
                        st.download_button(
                            label="⬇️ Download Video",
                            data=video_file,
                            file_name="narration_video.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )
                except Exception as e:
                    logger.error("Failed to load video for download", exc_info=True)
                    
        # --- Results Section ---
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader(f"📑 Results ({len(pages)} Pages)")
        
        narrations = get_all_narrations()
        
        for i, page in enumerate(pages):
            page_narration = next((n for n in narrations if n["page"] == page['page_number']), None)
            
            # Status Indicators
            status_icons = ""
            if page_narration:
                status_icons += " ✅ Narration Ready"
                if page['page_number'] in st.session_state["audio_map"]:
                    status_icons += " 🔊 Audio Ready"
                    
            with st.container(border=True):
                st.markdown(f"#### Page {page['page_number']} {status_icons}")
                st.markdown("<br>", unsafe_allow_html=True)
                
                col1, col2 = st.columns([2, 3]) # 40% Left, 60% Right
                
                with col1:
                    st.image(page['image_path'], width='stretch')
                    
                with col2:
                    if page_narration:
                        st.markdown("**Narration Script:**")
                        st.write(page_narration["text"])
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        if page['page_number'] in st.session_state["audio_map"]:
                            st.audio(st.session_state["audio_map"][page['page_number']])
                        else:
                            if st.button("Generate Audio", key=f"audio_btn_{i}", use_container_width=True):
                                with st.spinner("Generating audio..."):
                                    try:
                                        audio_path = generate_audio(
                                            text=page_narration["text"],
                                            user_id=user_id,
                                            page=page['page_number'],
                                            voice_model=selected_voice,
                                            speed=selected_speed
                                        )
                                        st.session_state["audio_map"][page['page_number']] = audio_path
                                        st.rerun()
                                    except Exception as e:
                                        logger.error(f"Failed to generate audio for page {page['page_number']}", exc_info=True)
                                        st.error("Failed to generate audio.")
                    else:
                        st.info("No narration generated yet.")
                        if st.button("Generate Narration", key=f"narrate_btn_{i}", use_container_width=True):
                            with st.spinner("Generating narration..."):
                                try:
                                    narration = generate_narration(
                                        page_text=page['text'],
                                        context=None,
                                        user_id=user_id,
                                        image_path=page['image_path']
                                    )
                                    st.session_state["narrations"] = [n for n in st.session_state["narrations"] if n["page"] != page['page_number']]
                                    st.session_state["narrations"].append({
                                        "page": page['page_number'],
                                        "text": narration,
                                        "image_path": page['image_path']
                                    })
                                    st.rerun()
                                except Exception as e:
                                    logger.error(f"Failed to generate narration for page {page['page_number']}", exc_info=True)
                                    st.error("Failed to generate narration.")

def main():
    if "pages" not in st.session_state:
        st.session_state["pages"] = []
    if "narrations" not in st.session_state:
        st.session_state["narrations"] = []
    if "audio_map" not in st.session_state:
        st.session_state["audio_map"] = {}
    if "video_path" not in st.session_state:
        st.session_state["video_path"] = None

    # Inject Custom CSS
    inject_custom_css()
    
    # Handle any OAuth callbacks from Supabase
    handle_oauth_callback()
    
    # Get the current logged-in user
    user = get_current_user(st.session_state)

    if user is None:
        # Centered landing page
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div class="hero-header">
                <h1>🎙️ PDF to Narration Studio</h1>
                <p>Turn PDFs into engaging voice narration instantly</p>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            with st.container(border=True):
                st.markdown("<div style='text-align: center; padding: 10px;'>", unsafe_allow_html=True)
                st.markdown("### Welcome Back")
                st.markdown("<p style='color: gray;'>Please log in to continue</p>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Continue with Google", use_container_width=True):
                    login_with_google()
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        # Sidebar Navigation
        st.sidebar.markdown(f"**👤 {user.email}**")
        st.sidebar.markdown("---")
        
        page = st.sidebar.radio("Navigation", ["Dashboard", "API Keys Settings"], label_visibility="collapsed")
        
        st.sidebar.markdown("---")
        if st.sidebar.button("Logout", use_container_width=True):
            logger.info(f"User {user.id} requested logout")
            logout()
            for key in ["show_key_form", "pages", "narrations", "audio_map", "video_path"]:
                st.session_state.pop(key, None)
            st.rerun()
            
        # Render Selected Page
        if page == "Dashboard":
            render_dashboard(user.id)
        elif page == "API Keys Settings":
            render_api_keys_settings(user.id)

if __name__ == "__main__":
    main()
