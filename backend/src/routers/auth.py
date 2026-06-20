from fastapi import APIRouter, HTTPException

from backend.src.models.user import User
from backend.src.types.user import LoginPayload

router = APIRouter(tags=["auth"])


@router.post("/login")
def login(payload: LoginPayload):
    try:
        user = User.login(
            username=payload.username.strip(),
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return {"data": user}


@router.get("/current_user")
def current_user(username: str):
    user = User.get_by_username(username.strip())

    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    return {"data": user}
