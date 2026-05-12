import re
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from auth.core import create_access_token, hash_password, verify_password
from auth.dependencies import get_current_user, require_admin
from auth.email import send_credentials_email, send_reset_email
from config import BASE_URL, FRONTEND_URL, TEST_MODE
from database import get_db
from models.email_token import EmailToken
from models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

_USERNAME_RE = re.compile(r'^[a-zA-Z0-9._-]{3,32}$')
_EMAIL_RE    = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


# ── Login ─────────────────────────────────────────────────────────────────────

_DUMMY_HASH = hash_password("dummy-constant-time-check")


@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form.username).first()
    candidate_hash = user.hashed_password if user else _DUMMY_HASH
    password_ok = verify_password(form.password, candidate_hash)
    if not user or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Cuenta pendiente de verificación. Revisa tu correo electrónico.",
        )

    token = create_access_token({"sub": user.id, "role": user.role, "username": user.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
    }


# ── Me ────────────────────────────────────────────────────────────────────────

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
    email: str
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

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("Formato de correo electrónico inválido")
        return v


@router.post("/users", status_code=201)
def create_user(
    body: CreateUserBody,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if body.role not in ("admin", "user"):
        raise HTTPException(400, "El rol debe ser 'admin' o 'user'")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(409, f"El usuario '{body.username}' ya existe")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(409, "Ese correo ya está registrado")

    temp_password = secrets.token_urlsafe(10)
    new_user = User(
        id=str(uuid.uuid4()),
        username=body.username,
        hashed_password=hash_password(temp_password),
        role=body.role,
        is_active=False,
        email=body.email,
    )
    db.add(new_user)
    db.flush()

    verify_token = secrets.token_urlsafe(32)
    db.add(EmailToken(
        id=str(uuid.uuid4()),
        user_id=new_user.id,
        token=verify_token,
        type="verify",
        expires_at=datetime.utcnow() + timedelta(hours=48),
    ))
    db.commit()

    verify_url = f"{BASE_URL}/auth/verify-email?token={verify_token}"
    send_credentials_email(body.email, body.username, temp_password, verify_url)

    result: dict = {"id": new_user.id, "username": new_user.username, "role": new_user.role}
    if TEST_MODE:
        result["verify_token"] = verify_token
        result["temp_password"] = temp_password
    return result


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(token: str, db: Session = Depends(get_db)):
    def _page(ok: bool, title: str, message: str) -> str:
        color = "#4a7a4f" if ok else "#a8453a"
        bg    = "#e0ecde" if ok else "#f6e0db"
        icon  = "✓" if ok else "✗"
        return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>{title} — MUA Biodiversidad</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:system-ui,sans-serif;background:#f7f5ee;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.wrap{{max-width:420px;width:100%;padding:16px}}
.header{{background:#2E5339;border-radius:10px 10px 0 0;padding:22px 28px}}
.header h1{{color:#C5D86D;font-size:18px;margin:0}}
.header p{{color:#8FB996;font-size:11px;margin:4px 0 0}}
.body{{background:#fff;border:1px solid #e3dfce;border-top:none;border-radius:0 0 10px 10px;padding:32px;text-align:center}}
.icon{{font-size:48px;color:{color};margin-bottom:12px}}
.badge{{display:inline-block;background:{bg};color:{color};padding:4px 14px;border-radius:99px;font-size:12px;font-weight:700;margin-bottom:16px}}
h2{{color:#1c2620;font-size:20px;margin:0 0 12px}}
p{{color:#4a544c;font-size:14px;line-height:1.6;margin:0 0 24px}}
a{{display:inline-block;background:#C5D86D;color:#1f3a27;font-weight:700;font-size:13px;padding:10px 22px;border-radius:7px;text-decoration:none}}
</style></head>
<body><div class="wrap">
<div class="header"><h1>✦ MUA Biodiversidad</h1><p>Sistema de gestión de colecciones</p></div>
<div class="body">
<div class="icon">{icon}</div>
<div class="badge">{'Cuenta activada' if ok else 'Enlace inválido'}</div>
<h2>{title}</h2>
<p>{message}</p>
<a href="{FRONTEND_URL}">{'Iniciar sesión →' if ok else 'Volver al inicio →'}</a>
</div></div></body></html>"""

    record = db.query(EmailToken).filter(
        EmailToken.token == token,
        EmailToken.type  == "verify",
    ).first()

    if not record:
        return _page(False, "Enlace no válido", "El enlace de verificación no existe o ya fue utilizado.")
    if record.used:
        return _page(False, "Ya verificado", "Este enlace ya fue utilizado. Tu cuenta debería estar activa.")
    if datetime.utcnow() > record.expires_at:
        return _page(False, "Enlace expirado", "El enlace ha expirado (48 h). Pide al administrador que reenvíe la invitación.")

    record.used = True
    user = db.get(User, record.user_id)
    if user:
        user.is_active = True
    db.commit()

    name = user.username if user else ""
    return _page(True, "Correo verificado", f"Tu cuenta <strong>{name}</strong> está activa. Ya puedes iniciar sesión con las credenciales que recibiste por correo.")


# ── Recuperación de contraseña ─────────────────────────────────────────────────

class ForgotPasswordBody(BaseModel):
    email: str


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()

    reset_token_val = None
    if user and user.is_active:
        # Invalidate previous unused reset tokens for this user
        for old in db.query(EmailToken).filter(
            EmailToken.user_id == user.id,
            EmailToken.type    == "reset",
            EmailToken.used    == False,
        ).all():
            old.used = True

        reset_token_val = secrets.token_urlsafe(32)
        db.add(EmailToken(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token=reset_token_val,
            type="reset",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        ))
        db.commit()

        reset_url = f"{FRONTEND_URL}?reset_token={reset_token_val}"
        send_reset_email(body.email, user.username, reset_url)

    msg = {"message": "Si ese correo está registrado, recibirás un enlace en breve."}
    if TEST_MODE and reset_token_val:
        msg["reset_token"] = reset_token_val
    return msg


class ResetPasswordBody(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


@router.post("/reset-password")
def reset_password(body: ResetPasswordBody, db: Session = Depends(get_db)):
    record = db.query(EmailToken).filter(
        EmailToken.token == body.token,
        EmailToken.type  == "reset",
    ).first()

    if not record or record.used:
        raise HTTPException(400, "El enlace de recuperación no es válido o ya fue utilizado")
    if datetime.utcnow() > record.expires_at:
        raise HTTPException(400, "El enlace de recuperación ha expirado")

    record.used = True
    user = db.get(User, record.user_id)
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"message": "Contraseña actualizada correctamente"}


# ── Listado y eliminación (solo admin) ────────────────────────────────────────

@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    users = db.query(User).all()
    return [
        {"id": u.id, "username": u.username, "role": u.role, "is_active": u.is_active, "email": u.email}
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
