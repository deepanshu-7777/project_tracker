from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from backend.database import get_connection, get_cursor
from backend.auth.hashing import hash_password, verify_password
from backend.auth.jwt_handler import create_access_token
from backend.auth.dependencies import get_current_user
from fastapi import Depends

router = APIRouter()

# ---------- Schemas ----------

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "member"   # default is member

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# ---------- Routes ----------

@router.post("/signup", status_code=201)
def signup(data: SignupRequest):
    conn = get_connection()
    cursor = get_cursor(conn)

    # Check if email already exists
    cursor.execute("SELECT id FROM users WHERE email = %s", (data.email,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validate role
    if data.role not in ["admin", "member"]:
        raise HTTPException(status_code=400, detail="Role must be admin or member")

    # Hash password and save
    hashed = hash_password(data.password)
    cursor.execute(
        "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
        (data.name, data.email, hashed, data.role)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "User registered successfully"}


@router.post("/login")
def login(data: LoginRequest):
    conn = get_connection()
    cursor = get_cursor(conn)

    # Find user by email
    cursor.execute("SELECT * FROM users WHERE email = %s", (data.email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Verify password
    if not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Generate JWT token
    token = create_access_token({
        "user_id": user["id"],
        "email": user["email"],
        "role": user["role"]
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        }
    }


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user