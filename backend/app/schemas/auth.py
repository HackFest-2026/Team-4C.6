import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(...)
    phone: Optional[str] = Field(default="", max_length=25)
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean):
            raise ValueError("Invalid email format.")
        return clean

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match.")
        return v


class UserLogin(BaseModel):
    email: str
    password: str
    remember_me: Optional[bool] = False

    @field_validator("email")
    @classmethod
    def sanitize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserProfileUpdate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = Field(default="", max_length=25)


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("confirm_new_password")
    @classmethod
    def check_new_passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("New passwords do not match.")
        return v


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    phone: Optional[str] = ""
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
