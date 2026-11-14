from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class UserModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
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


PRODUCT_VIEW = "engineering:product:view"
PRODUCT_ADD = "engineering:product:add"
PRODUCT_EDIT = "engineering:product:edit"
PLAN_VIEW = "plan:view"
PLAN_ADD = "plan:add"
PLAN_EDIT = "plan:edit"
PLAN_CONFIRM = "plan:confirm"
PLAN_CANCEL = "plan:cancel"
DEPARTMENT_WORK_ORDER_VIEW = "department:work-order:view"
DEPARTMENT_WORK_ORDER_OPERATE = "department:work-order:operate"


@dataclass(frozen=True, slots=True)
class ResolvedSession:
    user: UserResponse
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: UserResponse
    session_token: str
    csrf_token: str
    expires_at: datetime
