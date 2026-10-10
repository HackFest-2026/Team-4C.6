import uuid
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status

from app.schemas.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    UserProfileUpdate,
    PasswordChange,
    TokenResponse,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from app.db.session import get_db_connection

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse)
def register_user(req: UserRegister):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if email is already registered
    cursor.execute("SELECT id FROM users WHERE email = ?", (req.email,))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    pwd_hash, salt = hash_password(req.password)
    now = datetime.now(timezone.utc).isoformat()

    cursor.execute(
        """
        INSERT INTO users (id, full_name, email, phone, password_hash, salt, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, req.full_name.strip(), req.email, req.phone or "", pwd_hash, salt, now, now),
    )
    conn.commit()
    conn.close()

    token = create_access_token(user_id=user_id, email=req.email)
    user_resp = UserResponse(
        id=user_id,
        full_name=req.full_name.strip(),
        email=req.email,
        phone=req.phone or "",
        created_at=now,
    )
    return TokenResponse(access_token=token, token_type="bearer", user=user_resp)


@router.post("/login", response_model=TokenResponse)
def login_user(req: UserLogin):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email = ?", (req.email,))
    row = cursor.fetchone()
    conn.close()

    if not row or not verify_password(req.password, row["password_hash"], row["salt"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # 30 days token if remember_me is true, otherwise 7 days
    expires_seconds = 86400 * 30 if req.remember_me else 86400 * 7
    token = create_access_token(user_id=row["id"], email=row["email"], expires_in_seconds=expires_seconds)

    user_resp = UserResponse(
        id=row["id"],
        full_name=row["full_name"],
        email=row["email"],
        phone=row["phone"] or "",
        created_at=row["created_at"],
    )
    return TokenResponse(access_token=token, token_type="bearer", user=user_resp)


@router.get("/me", response_model=UserResponse)
def get_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        full_name=current_user["full_name"],
        email=current_user["email"],
        phone=current_user.get("phone", ""),
        created_at=current_user["created_at"],
    )


@router.put("/profile", response_model=UserResponse)
def update_profile(req: UserProfileUpdate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    cursor.execute(
        """
        UPDATE users
        SET full_name = ?, phone = ?, updated_at = ?
        WHERE id = ?
        """,
        (req.full_name.strip(), req.phone or "", now, current_user["id"]),
    )
    conn.commit()
    conn.close()

    return UserResponse(
        id=current_user["id"],
        full_name=req.full_name.strip(),
        email=current_user["email"],
        phone=req.phone or "",
        created_at=current_user["created_at"],
    )


@router.post("/change-password")
def change_password(req: PasswordChange, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT password_hash, salt FROM users WHERE id = ?", (current_user["id"],))
    row = cursor.fetchone()
    if not row or not verify_password(req.current_password, row["password_hash"], row["salt"]):
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if req.current_password == req.new_password:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as the current password.",
        )

    new_hash, new_salt = hash_password(req.new_password)
    now = datetime.now(timezone.utc).isoformat()

    cursor.execute(
        """
        UPDATE users
        SET password_hash = ?, salt = ?, updated_at = ?
        WHERE id = ?
        """,
        (new_hash, new_salt, now, current_user["id"]),
    )
    conn.commit()
    conn.close()

    return {"status": "success", "message": "Password changed successfully."}


@router.post("/logout")
def logout_user():
    return {"status": "success", "message": "Logged out successfully."}
