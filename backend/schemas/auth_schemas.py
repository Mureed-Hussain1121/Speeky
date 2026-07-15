from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class SignupSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    # .regex(
    #     r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).+$",
    #     "Password must contain uppercase, lowercase, number, and special character.",
    # )
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)


class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class ForgotSchema(BaseModel):
    email: EmailStr


class ResetSchema(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8)
    # .regex(
    #     r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).+$",
    #     "Password must contain uppercase, lowercase, number, and special character.",
    # )
