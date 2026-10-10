import hmac
import hashlib
import secrets
import json
import base64
import time
from typing import Optional, Dict, Any, Tuple
from fastapi import HTTPException, Header, Depends, status

from app.core.config import settings

SALT_BYTES = 16
HASH_ITERATIONS = 100000


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with a cryptographically secure salt.
    Returns (hex_hash, hex_salt).
    """
    if not salt:
        salt_bytes = secrets.token_bytes(SALT_BYTES)
        salt = salt_bytes.hex()
    else:
        salt_bytes = bytes.fromhex(salt)
        
    pw_bytes = password.encode("utf-8")
    derived = hashlib.pbkdf2_hmac("sha256", pw_bytes, salt_bytes, HASH_ITERATIONS)
    return derived.hex(), salt


def verify_password(plain_password: str, password_hash: str, salt: str) -> bool:
    """
    Constant-time verification of password against stored PBKDF2-HMAC-SHA256 hash.
    """
    computed_hash, _ = hash_password(plain_password, salt)
    return hmac.compare_digest(computed_hash, password_hash)


def create_access_token(user_id: str, email: str, expires_in_seconds: int = 86400 * 7) -> str:
    """
    Creates a signed, tamper-proof session token.
    Format: base64(payload).signature
    """
    payload = {
        "sub": user_id,
        "email": email,
        "exp": int(time.time()) + expires_in_seconds,
        "iat": int(time.time()),
    }
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    
    secret = settings.SECRET_KEY.encode("utf-8")
    sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verifies the HMAC signature and expiration timestamp of the token.
    Returns decoded payload if valid, None otherwise.
    """
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        
        # Verify HMAC signature
        secret = settings.SECRET_KEY.encode("utf-8")
        expected_sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
            
        # Decode base64 payload
        padding = "=" * (4 - len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_bytes.decode("utf-8"))
        
        # Check expiration
        if payload.get("exp", 0) < time.time():
            return None
            
        return payload
    except Exception:
        return None


def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """
    Extracts and validates user from Authorization header if present.
    Returns user dict or None.
    """
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1]
    payload = verify_access_token(token)
    if not payload:
        return None
        
    user_id = payload.get("sub")
    if not user_id:
        return None
        
    from app.db.session import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, email, phone, created_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "phone": row["phone"] or "",
        "created_at": row["created_at"],
    }


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Enforces authentication. Raises 401 Unauthorized if token is missing or invalid.
    """
    user = get_current_user_optional(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

