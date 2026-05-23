import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backend.config.settings import settings

def _get_key() -> bytes:
    key_str = settings.ENCRYPTION_KEY
    if not key_str:
        raise ValueError("ENCRYPTION_KEY is not set in the environment")
    
    # Try to decode if base64, else use raw string
    try:
        key = base64.b64decode(key_str)
        if len(key) == 32:
            return key
    except Exception:
        pass
        
    # Ensure exactly 32 bytes
    key = key_str.encode('utf-8')
    if len(key) < 32:
        key = key.ljust(32, b'\0')
    elif len(key) > 32:
        key = key[:32]
        
    return key

def encrypt(plaintext: str) -> tuple[str, str]:
    """Encrypts a plaintext string and returns (ciphertext_b64, iv_b64)."""
    if not plaintext:
        return "", ""
    
    key = _get_key()
    aesgcm = AESGCM(key)
    iv_bytes = os.urandom(12) # 96-bit IV recommended for GCM
    
    ciphertext = aesgcm.encrypt(iv_bytes, plaintext.encode('utf-8'), None)
    
    return base64.b64encode(ciphertext).decode('utf-8'), base64.b64encode(iv_bytes).decode('utf-8')

def decrypt(ciphertext_b64: str, iv_b64: str) -> str:
    """Decrypts a base64 ciphertext using the given base64 IV."""
    if not ciphertext_b64 or not iv_b64:
        return ""
        
    key = _get_key()
    aesgcm = AESGCM(key)
    
    iv = base64.b64decode(iv_b64)
    ciphertext = base64.b64decode(ciphertext_b64)
    
    plaintext = aesgcm.decrypt(iv, ciphertext, None)
    return plaintext.decode('utf-8')
