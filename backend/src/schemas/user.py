from pydantic import BaseModel, ConfigDict, Field

class UserModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginPayload(UserModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)


class UserResponse(UserModel):
    id: int
    username: str
    name: str
    is_system: bool
    role: str
    department_code: str | None
    permissions: list[str]


class LoginResponse(UserModel):
    data: UserResponse
    csrfToken: str


class CurrentUserResponse(UserModel):
    data: UserResponse | None
    csrfToken: str | None = None


class MessageResponse(UserModel):
    message: str
