import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.core import create_access_token, hash_password, verify_password
from auth.dependencies import get_current_user, require_admin
from database import get_db
from models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Usuario desactivado")

    token = create_access_token({"sub": user.id, "role": user.role, "username": user.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
    }


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }


# ── Gestión de usuarios (solo admin) ─────────────────────────────────────────

class CreateUserBody(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"


@router.post("/users", status_code=201)
def create_user(
    body: CreateUserBody,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if body.role not in ("admin", "user"):
        raise HTTPException(400, "El rol debe ser 'admin' o 'user'")
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(409, f"El usuario '{body.username}' ya existe")

    new_user = User(
        id=str(uuid.uuid4()),
        username=body.username,
        hashed_password=hash_password(body.password),
        role=body.role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    return {"id": new_user.id, "username": new_user.username, "role": new_user.role}


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    users = db.query(User).all()
    return [
        {"id": u.id, "username": u.username, "role": u.role, "is_active": u.is_active}
        for u in users
    ]


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    if user_id == current_admin.id:
        raise HTTPException(400, "No puedes eliminar tu propia cuenta")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    db.delete(user)
    db.commit()
