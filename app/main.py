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
from utils.logger import get_logger

logger = get_logger(__name__)

def get_all_narrations():
    """Returns an ordered list of all structured narration objects."""
    if "narrations" not in st.session_state:
        return []
    return sorted(st.session_state["narrations"], key=lambda x: x["page"])

st.set_page_config(page_title="PDF to Narration Video Generator", layout="wide")

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
    st.header("Dashboard")
    
    if not has_api_keys(user_id):
        st.warning("Please configure your API keys in the Settings tab first.")
        return
        
    # PDF Upload UI
    st.subheader("Upload PDF")
    with st.container():
        uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])
        
        if uploaded_file is not None:
            if st.button("Process PDF"):
                logger.info(f"User {user_id} triggered PDF processing")
                with st.spinner("Uploading and processing PDF..."):
                    try:
                        # 1. Upload to Supabase
                        file_bytes = uploaded_file.getvalue()
                        storage_path = upload_pdf(file_bytes, user_id)
                        
                        # 2. Download locally for processing
                        local_pdf_path = download_pdf(storage_path)
                        
                        # 3. Split into pages
                        pages = split_pdf_to_pages(local_pdf_path)
                        
                        # Store in session state so it persists across button clicks
                        st.session_state.pdf_pages = pages
                        logger.info("Successfully processed PDF and stored pages in session state")
                        
                        # Clean up the downloaded PDF temp file
                        if os.path.exists(local_pdf_path):
                            os.remove(local_pdf_path)
                            
                    except Exception as e:
                        logger.error("Error occurred during PDF processing flow", exc_info=True)
                        st.error("Error processing PDF. Please check the logs.")

    if "pdf_pages" in st.session_state:
        st.markdown("---")
        st.subheader("Processed Pages")
        pages = st.session_state.pdf_pages
        st.success(f"Processed {len(pages)} pages!")
        if "narrations" not in st.session_state:
            st.session_state["narrations"] = []
            
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("Generate Narration for All Pages"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, page in enumerate(pages):
                    page_num = page['page_number']
                    
                    if any(n["page"] == page_num for n in st.session_state["narrations"]):
                        logger.info(f"Skipping page {page_num}, narration already exists.")
                        continue
                        
                    status_text.text(f"Generating narration for page {page_num}...")
                    
                    try:
                        narration = generate_narration(
                            page_text=page['text'],
                            context=None,
                            user_id=user_id,
                            image_path=page['image_path']
                        )
                        st.session_state["narrations"].append({
                            "page": page_num,
                            "text": narration,
                            "image_path": page['image_path']
                        })
                        logger.info("Narrations structured for pipeline")
                        logger.info(f"Completed page {page_num}")
                    except Exception as e:
                        logger.error(f"Failed to generate narration for page {page_num}", exc_info=True)
                        st.toast(f"Failed to generate narration for page {page_num}")
                        
                    progress_bar.progress((i + 1) / len(pages))
                    time.sleep(1)
                    
                status_text.text("Completed all pages!")
                st.rerun()
                
        with col_btn2:
            if st.button("Generate Audio for All Pages"):
                narrations = get_all_narrations()
                if not narrations:
                    st.warning("Please generate narrations first.")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i, narration_obj in enumerate(narrations):
                        page_num = narration_obj["page"]
                        if "audio_path" in narration_obj:
                            logger.info(f"Skipping audio for page {page_num}, already exists.")
                            continue
                            
                        status_text.text(f"Generating audio for page {page_num}...")
                        
                        try:
                            audio_path = generate_audio(
                                text=narration_obj["text"],
                                user_id=user_id,
                                page=page_num
                            )
                            narration_obj["audio_path"] = audio_path
                            logger.info(f"Completed audio for page {page_num}")
                        except Exception as e:
                            logger.error(f"Failed to generate audio for page {page_num}", exc_info=True)
                            st.toast(f"Failed to generate audio for page {page_num}")
                            
                        progress_bar.progress((i + 1) / len(narrations))
                        time.sleep(1)
                        
                    status_text.text("Completed audio generation for all pages!")
                    st.rerun()
            
        # Display pages
        for i, page in enumerate(pages):
            with st.container():
                st.markdown(f"### Page {page['page_number']}")
                
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.image(page['image_path'], use_container_width=True)
                    
                with col2:
                    text_preview = page['text'][:200] + "..." if len(page['text']) > 200 else page['text']
                    st.write("**Text Preview:**")
                    st.info(text_preview)
                    
                    # Narration Generation
                    if st.button("Generate Narration", key=f"narrate_btn_{i}"):
                        logger.info(f"User {user_id} requested narration for page {page['page_number']}")
                        with st.spinner("Generating narration..."):
                            try:
                                narration = generate_narration(
                                    page_text=page['text'],
                                    context=None,
                                    user_id=user_id,
                                    image_path=page['image_path']
                                )
                                
                                if "narrations" not in st.session_state:
                                    st.session_state["narrations"] = []
                                    
                                # Remove existing if regenerating
                                st.session_state["narrations"] = [n for n in st.session_state["narrations"] if n["page"] != page['page_number']]
                                
                                st.session_state["narrations"].append({
                                    "page": page['page_number'],
                                    "text": narration,
                                    "image_path": page['image_path']
                                })
                                logger.info("Narrations structured for pipeline")
                                logger.info(f"Successfully generated narration for page {page['page_number']}")
                            except Exception as e:
                                logger.error(f"Failed to generate narration for page {page['page_number']}", exc_info=True)
                                st.error("Failed to generate narration.")
                                
                    narrations = get_all_narrations()
                    page_narration = next((n for n in narrations if n["page"] == page['page_number']), None)
                    
                    if page_narration:
                        st.write("**Narration:**")
                        st.success(page_narration["text"])
                        
                        if "audio_path" in page_narration:
                            st.audio(page_narration["audio_path"])
                        else:
                            if st.button("Generate Audio", key=f"audio_btn_{i}"):
                                logger.info(f"User {user_id} requested audio for page {page['page_number']}")
                                with st.spinner("Generating audio..."):
                                    try:
                                        audio_path = generate_audio(
                                            text=page_narration["text"],
                                            user_id=user_id,
                                            page=page['page_number']
                                        )
                                        page_narration["audio_path"] = audio_path
                                        logger.info(f"Successfully generated audio for page {page['page_number']}")
                                        st.rerun()
                                    except Exception as e:
                                        logger.error(f"Failed to generate audio for page {page['page_number']}", exc_info=True)
                                        st.error("Failed to generate audio.")
                        
                st.markdown("---")

def main():
    # Handle any OAuth callbacks from Supabase
    handle_oauth_callback()

    # Get the current logged-in user
    user = get_current_user(st.session_state)

    if user is None:
        st.title("PDF to Narration Video Generator")
        # Show login screen
        st.write("Please log in to continue.")
        if st.button("Continue with Google"):
            login_with_google()
    else:
        # Sidebar Navigation
        st.sidebar.title(f"Welcome, {user.email}")
        st.sidebar.markdown("---")
        
        page = st.sidebar.radio("Navigation", ["Dashboard", "API Keys Settings"])
        
        st.sidebar.markdown("---")
        if st.sidebar.button("Logout"):
            logger.info(f"User {user.id} requested logout")
            logout()
            # Clear UI specific state
            for key in ["show_key_form", "pdf_pages"]:
                st.session_state.pop(key, None)
            st.rerun()
            
        # Render Selected Page
        if page == "Dashboard":
            render_dashboard(user.id)
        elif page == "API Keys Settings":
            render_api_keys_settings(user.id)

if __name__ == "__main__":
    main()
