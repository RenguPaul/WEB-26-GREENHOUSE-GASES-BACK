from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )


class UserRegisterResponse(BaseModel):
    id: int
    username: str


class AuthStubResponse(BaseModel):
    message: str