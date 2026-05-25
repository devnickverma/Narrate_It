from fastapi import APIRouter, HTTPException, status
from backend.models.auth import SendOTPRequest, VerifyOTPRequest
from backend.services.auth_service import send_otp_code, verify_otp_code
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/otp/send")
async def send_otp(payload: SendOTPRequest):
    logger.info(f"Received send OTP request for email: {payload.email}")
    success, message = send_otp_code(payload.email)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )
    
    from backend.config.settings import settings
    return {
        "status": "success",
        "message": message,
        "otp_required": settings.OTP_LOGIN_MODE
    }

@router.post("/otp/verify")
async def verify_otp(payload: VerifyOTPRequest):
    logger.info(f"Received verify OTP request for email: {payload.email}")
    success, result = verify_otp_code(payload.email, payload.token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(result)
        )
    
    # Safely extract user object and tokens
    user_obj = None
    access_token = None
    refresh_token = None
    
    if hasattr(result, "user") and result.user:
        user_obj = result.user
    if hasattr(result, "session") and result.session:
        access_token = getattr(result.session, "access_token", None)
        refresh_token = getattr(result.session, "refresh_token", None)
        if not user_obj and hasattr(result.session, "user") and result.session.user:
            user_obj = result.session.user
            
    email = user_obj.email if user_obj else payload.email
    return {
        "status": "success",
        "message": "Login successful!",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user_obj.id if user_obj else None,
            "email": email
        }
    }
