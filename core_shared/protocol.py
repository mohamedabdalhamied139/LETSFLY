"""Shared protocol models."""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

class UserRegister(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    display_name: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username", "display_name")
    @classmethod
    def normalize_names(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("يجب أن يحتوي الاسم على حرفين على الأقل بعد إزالة المسافات.")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("كلمة المرور لا يمكن أن تكون مسافات فقط.")
        # bcrypt processes at most 72 UTF-8 bytes. Reject longer new passwords
        # instead of allowing an implicit truncation that could create two
        # different passwords with the same effective bcrypt input.
        if len(value.encode("utf-8")) > 72:
            raise ValueError("كلمة المرور طويلة جدًا بالنسبة إلى نظام التشفير المستخدم.")
        return value

class UserLogin(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_login_username(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("اسم المستخدم غير صالح.")
        return value

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("current_password", "new_password")
    @classmethod
    def validate_change_password(cls, value: str, info) -> str:
        if not value.strip():
            raise ValueError("كلمة المرور لا يمكن أن تكون مسافات فقط.")
        if info.field_name == "new_password" and len(value.encode("utf-8")) > 72:
            raise ValueError("كلمة المرور طويلة جدًا بالنسبة إلى نظام التشفير المستخدم.")
        return value

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class CreateRoomRequest(BaseModel):
    game: str = Field(default="UNO", min_length=1, max_length=32)

class StartGameRequest(BaseModel):
    target_score: Optional[int] = Field(default=None, ge=1, le=9999)
    rules: Dict[str, Any] = Field(default_factory=dict, max_length=32)

    @field_validator("rules")
    @classmethod
    def validate_rules_payload(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        import json
        if len(json.dumps(value, ensure_ascii=False, separators=(",", ":"))) > 8192:
            raise ValueError("rules payload is too large")
        return value

class RoomActionRequest(BaseModel):
    action: str = Field(min_length=1, max_length=40)
    card_id: Optional[str] = Field(default="", max_length=100)
    chosen_color: Optional[str] = Field(default="", max_length=40)
    target_player_id: Optional[str] = Field(default="", max_length=100)
    side: Optional[str] = Field(default="", max_length=20)
    data: Optional[Dict[str, Any]] = Field(default=None)

class ChatMessage(BaseModel):
    text: str = Field(min_length=1, max_length=500)

class TargetUserRequest(BaseModel):
    target_user_id: Optional[int] = None
    replacement_user_id: Optional[int] = None
    is_bot: Optional[bool] = False

class VoiceModeRequest(BaseModel):
    mode: str = Field(min_length=1, max_length=20)

