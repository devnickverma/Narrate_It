from backend.services.supabase_client import get_supabase_client
from backend.utils.logger import get_logger

logger = get_logger(__name__)

def send_otp_code(email: str):
    """Send a passwordless OTP code to the user's email using Supabase."""
    logger.info(f"Initiating OTP delivery for email: {email}")
    supabase = get_supabase_client()
    try:
        supabase.auth.sign_in_with_otp({
            "email": email,
            "options": {
                "should_create_user": True
            }
        })
        logger.info(f"Successfully requested OTP email for {email}")
        return True, "One-time code sent successfully! Please check your email inbox."
    except Exception as e:
        logger.error(f"Failed to deliver OTP code for {email}", exc_info=True)
        return False, f"Delivery failed: {str(e)}"

def verify_otp_code(email: str, token: str):
    """Verify the OTP code token via Supabase."""
    logger.info(f"Verifying OTP code for user: {email}")
    supabase = get_supabase_client()
    try:
        res = supabase.auth.verify_otp({
            "email": email,
            "token": token,
            "type": "email"
        })
        if res and res.user:
            logger.info(f"Successfully verified and authenticated user: {res.user.email}")
            return True, res
        else:
            logger.error("Authentication failed during OTP code confirmation - no user returned.")
            return False, "Failed to authenticate. Try again."
    except Exception as e:
        logger.error(f"OTP verification failed for user {email}", exc_info=True)
        return False, f"Verification failed: {str(e)}"
