from pydantic import BaseModel, Field, ConfigDict


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=255, pattern=r"^[A-Za-zА-Яа-яЁё0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class UserRegisterResponse(BaseModel):
    id: int
    username: str
    role: str


class AuthResponse(BaseModel):
    message: str
    user_id: int
    username: str
    role: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str
