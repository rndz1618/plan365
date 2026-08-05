"""Auth routes."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import current_user, make_token
from app.auth_utils import verify_pw, hash_pw
from app.database import db, row
from app.models import Token, UserCreate

router = APIRouter(tags=["auth"])

@router.post("/auth/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    with db() as c:
        u = c.execute("SELECT * FROM users WHERE username=? OR email=?", (form.username, form.username)).fetchone()
        if not u or not verify_pw(form.password, u["hashed_password"]):
            raise HTTPException(401, "Incorrect credentials")
        if not u["is_active"]: raise HTTPException(401, "Inactive")
        return {"access_token": make_token({"sub": str(u["id"])}), "token_type": "bearer"}

@router.post("/auth/register")
async def register(p: UserCreate):
    with db() as c:
        allow = c.execute("SELECT value FROM settings WHERE key='allow_registration'").fetchone()
        if allow and allow["value"] != "true": raise HTTPException(403, "Registration disabled")
        if c.execute("SELECT id FROM users WHERE username=? OR email=?", (p.username, p.email)).fetchone():
            raise HTTPException(400, "Username or email exists")
        cur = c.execute("INSERT INTO users (username,email,hashed_password,full_name,role) VALUES (?,?,?,?,'user')",
                        (p.username, p.email, hash_pw(p.password), p.full_name))
        uid = cur.lastrowid
        c.execute("INSERT INTO user_preferences (user_id) VALUES (?)", (uid,))
        return row(c.execute("SELECT id,username,email,full_name,role,is_active FROM users WHERE id=?", (uid,)).fetchone())

@router.get("/auth/me")
async def me(u=Depends(current_user)): return u


