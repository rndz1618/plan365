"""JWT auth dependencies and access helpers."""
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_HOURS
from app.database import db, row
from app.auth_utils import hash_pw, verify_pw  # re-export

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def make_token(data: dict, exp=None) -> str:
    d = data.copy()
    d["exp"] = datetime.utcnow() + (exp or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    return jwt.encode(d, SECRET_KEY, algorithm=ALGORITHM)


async def current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("sub")
        if uid is None:
            raise HTTPException(401, "Invalid token")
        uid = int(uid)
    except JWTError:
        raise HTTPException(401, "Invalid token")
    with db() as c:
        u = c.execute(
            "SELECT id,username,email,full_name,role,is_active FROM users WHERE id=?",
            (uid,),
        ).fetchone()
        if not u or not u["is_active"]:
            raise HTTPException(401, "Invalid user")
        return row(u)


def require_admin(u=Depends(current_user)):
    if u["role"] != "admin":
        raise HTTPException(403, "Admin only")
    return u


def proj_role(c, uid, pid):
    u = c.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
    if u and u["role"] == "admin":
        return "owner"
    r = c.execute(
        "SELECT role FROM project_members WHERE project_id=? AND user_id=?",
        (pid, uid),
    ).fetchone()
    return r["role"] if r else None


def check_access(c, uid, pid, mins=None):
    if mins is None:
        mins = ["viewer"]
    role = proj_role(c, uid, pid)
    if not role:
        raise HTTPException(403, "No access")
    h = {"viewer": 1, "editor": 2, "owner": 3}
    if h.get(role, 0) < min(h.get(m, 0) for m in mins):
        raise HTTPException(403, "Insufficient role")
    return role
