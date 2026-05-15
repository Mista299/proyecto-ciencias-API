import sys
import os
import glob
import site
import uuid

_base = os.path.dirname(os.path.abspath(__file__))
for _pattern in [
    os.path.join(_base, ".venv", "lib", "python*", "site-packages"),
    os.path.join(_base, "..", ".venv", "lib", "python*", "site-packages"),
]:
    _matches = glob.glob(_pattern)
    if _matches:
        site.addsitedir(_matches[0])
        break

sys.path.insert(0, _base)

from database import SessionLocal, init_db
from models.user import User
from auth.core import hash_password

ADMIN_USERNAME = os.getenv("SEED_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "changeme123")

init_db()
db = SessionLocal()
try:
    existing = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    if existing:
        print(f"[seed] Usuario '{ADMIN_USERNAME}' ya existe — sin cambios.")
    else:
        admin = User(
            id=str(uuid.uuid4()),
            username=ADMIN_USERNAME,
            hashed_password=hash_password(ADMIN_PASSWORD),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"[seed] Admin '{ADMIN_USERNAME}' creado exitosamente.")
finally:
    db.close()
