import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from auth.core import create_access_token, hash_password, verify_password
from auth.dependencies import get_current_user, require_admin
from database import get_db
from models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

_USERNAME_RE = re.compile(r'^[a-zA-Z0-9._-]{3,32}$')


# ── Login ─────────────────────────────────────────────────────────────────────

_DUMMY_HASH = hash_password("dummy-constant-time-check")

@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form.username).first()
    # Always run verify_password to prevent username enumeration via timing
    candidate_hash = user.hashed_password if user else _DUMMY_HASH
    password_ok = verify_password(form.password, candidate_hash)
    if not user or not password_ok:
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

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "role": u.role,
        "is_active": u.is_active,
        "email": u.email,
    }


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return _user_dict(current_user)


class UpdateProfileBody(BaseModel):
    email: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "" and not _EMAIL_RE.match(v):
            raise ValueError("Formato de correo electrónico inválido")
        return v or None

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


@router.patch("/me")
def update_me(
    body: UpdateProfileBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.new_password is not None:
        if not body.current_password:
            raise HTTPException(400, "Debes ingresar tu contraseña actual para cambiarla")
        if not verify_password(body.current_password, current_user.hashed_password):
            raise HTTPException(400, "La contraseña actual es incorrecta")
        current_user.hashed_password = hash_password(body.new_password)

    if body.email is not None:
        existing = db.query(User).filter(
            User.email == body.email, User.id != current_user.id
        ).first()
        if existing:
            raise HTTPException(409, "Ese correo ya está en uso por otra cuenta")
        current_user.email = body.email

    db.commit()
    return _user_dict(current_user)


# ── Gestión de usuarios (solo admin) ─────────────────────────────────────────

class CreateUserBody(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "El username debe tener entre 3 y 32 caracteres y solo puede "
                "contener letras, números, puntos, guiones y guiones bajos."
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        return v


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
