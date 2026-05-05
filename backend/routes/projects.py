from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from backend.database import get_connection, get_cursor
from backend.auth.dependencies import get_current_user, require_admin

router = APIRouter()

# ---------- Schemas ----------

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class AddMemberRequest(BaseModel):
    user_id: int
    role: str = "member"

# ---------- Routes ----------

# Create project (Admin only)
@router.post("/", status_code=201)
def create_project(data: ProjectCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create projects")

    conn = get_connection()
    cursor = get_cursor(conn)

    cursor.execute(
        "INSERT INTO projects (name, description, owner_id) VALUES (%s, %s, %s)",
        (data.name, data.description, current_user["id"])
    )
    project_id = cursor.lastrowid

    # Auto-add creator as admin member
    cursor.execute(
        "INSERT INTO project_members (project_id, user_id, role) VALUES (%s, %s, %s)",
        (project_id, current_user["id"], "admin")
    )
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Project created", "project_id": project_id}


# Get all projects for current user
@router.get("/")
def get_projects(current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = get_cursor(conn)

    if current_user["role"] == "admin":
        # Admins see all projects
        cursor.execute("""
            SELECT p.*, u.name as owner_name
            FROM projects p
            JOIN users u ON p.owner_id = u.id
            ORDER BY p.created_at DESC
        """)
    else:
        # Members see only their projects
        cursor.execute("""
            SELECT p.*, u.name as owner_name
            FROM projects p
            JOIN users u ON p.owner_id = u.id
            JOIN project_members pm ON pm.project_id = p.id
            WHERE pm.user_id = %s
            ORDER BY p.created_at DESC
        """, (current_user["id"],))

    projects = cursor.fetchall()
    cursor.close()
    conn.close()
    return projects


# Get single project by ID
@router.get("/{project_id}")
def get_project(project_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = get_cursor(conn)

    cursor.execute("""
        SELECT p.*, u.name as owner_name
        FROM projects p
        JOIN users u ON p.owner_id = u.id
        WHERE p.id = %s
    """, (project_id,))
    project = cursor.fetchone()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check access for members
    if current_user["role"] != "admin":
        cursor.execute(
            "SELECT id FROM project_members WHERE project_id = %s AND user_id = %s",
            (project_id, current_user["id"])
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Access denied")

    cursor.close()
    conn.close()
    return project


# Update project (Admin only)
@router.put("/{project_id}")
def update_project(project_id: int, data: ProjectUpdate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update projects")

    conn = get_connection()
    cursor = get_cursor(conn)

    cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Project not found")

    if data.name:
        cursor.execute("UPDATE projects SET name = %s WHERE id = %s", (data.name, project_id))
    if data.description is not None:
        cursor.execute("UPDATE projects SET description = %s WHERE id = %s", (data.description, project_id))

    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Project updated"}


# Delete project (Admin only)
@router.delete("/{project_id}")
def delete_project(project_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete projects")

    conn = get_connection()
    cursor = get_cursor(conn)

    cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Project not found")

    cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Project deleted"}


# Add member to project (Admin only)
@router.post("/{project_id}/members")
def add_member(project_id: int, data: AddMemberRequest, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can add members")

    if data.role not in ["admin", "member"]:
        raise HTTPException(status_code=400, detail="Role must be admin or member")

    conn = get_connection()
    cursor = get_cursor(conn)

    # Check project exists
    cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Project not found")

    # Check user exists
    cursor.execute("SELECT id FROM users WHERE id = %s", (data.user_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="User not found")

    # Check already a member
    cursor.execute(
        "SELECT id FROM project_members WHERE project_id = %s AND user_id = %s",
        (project_id, data.user_id)
    )
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="User already a member")

    cursor.execute(
        "INSERT INTO project_members (project_id, user_id, role) VALUES (%s, %s, %s)",
        (project_id, data.user_id, data.role)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Member added successfully"}


# Get all members of a project
@router.get("/{project_id}/members")
def get_members(project_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = get_cursor(conn)

    cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Project not found")

    cursor.execute("""
        SELECT u.id, u.name, u.email, pm.role
        FROM project_members pm
        JOIN users u ON pm.user_id = u.id
        WHERE pm.project_id = %s
    """, (project_id,))

    members = cursor.fetchall()
    cursor.close()
    conn.close()
    return members


# Remove member from project (Admin only)
@router.delete("/{project_id}/members/{user_id}")
def remove_member(project_id: int, user_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can remove members")

    conn = get_connection()
    cursor = get_cursor(conn)

    cursor.execute(
        "SELECT id FROM project_members WHERE project_id = %s AND user_id = %s",
        (project_id, user_id)
    )
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Member not found")

    cursor.execute(
        "DELETE FROM project_members WHERE project_id = %s AND user_id = %s",
        (project_id, user_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Member removed"}