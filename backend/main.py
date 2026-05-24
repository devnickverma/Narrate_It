from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from backend.config.settings import settings
from backend.routes import health, auth, upload, generate, history, settings as settings_route
from backend.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade backend for NarrateIt PDF voiceover video generation.",
    version="1.0.0",
    debug=settings.DEBUG
)

# CORS configurations
origins = [
    "http://localhost:8501", # Legacy Streamlit UI
    "http://127.0.0.1:8501",
    "http://localhost:3000", # Future React/Next.js frontend
    "http://127.0.0.1:3000",
    "http://localhost:5500", # Local static server
    "http://127.0.0.1:5500"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register modular sub-routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(generate.router)
app.include_router(history.router)
app.include_router(settings_route.router)

@app.on_event("startup")
async def startup_diagnostics():
    logger.info("==================================================")
    logger.info(f"STARTING {settings.APP_NAME} RUNTIME DIAGNOSTICS")
    logger.info("==================================================")
    
    # 1. Trace all registered routes
    logger.info("Tracing registered API route endpoints:")
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        logger.info(f" - Route: {path} [Methods: {list(methods) if methods else 'N/A'}]")
        
    # 2. Validate Supabase connection
    logger.info("Verifying connection to Supabase...")
    try:
        from backend.services.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        # Verify connectivity by listing buckets in storage
        buckets = supabase.storage.list_buckets()
        logger.info("[SUCCESS] Supabase connection successfully established!")
        logger.info(f"[SUCCESS] Storage buckets verified: {[b.name for b in buckets] if buckets else 'None'}")
    except Exception as e:
        logger.error(f"[FAIL] Supabase initialization/connection failed: {str(e)}", exc_info=True)
        
    # 3. Validate Environmental Variables presence
    logger.info("Validating environment key configurations:")
    has_enc = bool(settings.ENCRYPTION_KEY)
    logger.info(f" - ENCRYPTION_KEY present: {has_enc}")
    if not has_enc:
        logger.warning("[WARNING] Warning: ENCRYPTION_KEY is missing!")
        
    logger.info("==================================================")

@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect roots requests to standard FastAPI Swagger documentation."""
    return RedirectResponse(url="/docs")

logger.info(f"Initialized {settings.APP_NAME} successfully.")
