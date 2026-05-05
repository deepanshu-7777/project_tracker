from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import date
from backend.database import get_connection, get_cursor
from backend.auth.dependencies import get_current_user

router = APIRouter()

# ---------- Schemas ----------

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    due_date: Optional[date] = None
    project_id: int
    assigned_to: Optional[int] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    assigned_to: Optional[int] = None

# ---------- Helper ----------

def check_project_access(cursor, project_id: int, user: dict):
    cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Project not found")

    if user["role"] != "admin":
        cursor.execute(
            "SELECT id FROM project_members WHERE project_id = %s AND user_id = %s",
            (project_id, user["id"])
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Access denied to this project")

# ---------- Routes ----------

# Create task (Admin only)
@router.post("/", status_code=201)
def create_task(data: TaskCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create tasks")

    if data.priority not in ["low", "medium", "high"]:
        raise HTTPException(status_code=400, detail="Priority must be low, medium, or high")

    conn = get_connection()
    cursor = get_cursor(conn)

    check_project_access(cursor, data.project_id, current_user)

    # Validate assignee is member of the project
    if data.assigned_to:
        cursor.execute(
            "SELECT id FROM project_members WHERE project_id = %s AND user_id = %s",
            (data.project_id, data.assigned_to)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=400, detail="Assigned user is not a member of this project")

    cursor.execute("""
        INSERT INTO tasks (title, description, priority, due_date, project_id, assigned_to, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        data.title,
        data.description,
        data.priority,
        data.due_date,
        data.project_id,
        data.assigned_to,
        current_user["id"]
    ))
    task_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Task created", "task_id": task_id}


# Get all tasks (filter by project)
@router.get("/")
def get_tasks(project_id: Optional[int] = None, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = get_cursor(conn)

    if current_user["role"] == "admin":
        if project_id:
            cursor.execute("""
                SELECT t.*, 
                       u1.name as assigned_to_name,
                       u2.name as created_by_name,
                       p.name as project_name
                FROM tasks t
                LEFT JOIN users u1 ON t.assigned_to = u1.id
                LEFT JOIN users u2 ON t.created_by = u2.id
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.project_id = %s
                ORDER BY t.created_at DESC
            """, (project_id,))
        else:
            cursor.execute("""
                SELECT t.*,
                       u1.name as assigned_to_name,
                       u2.name as created_by_name,
                       p.name as project_name
                FROM tasks t
                LEFT JOIN users u1 ON t.assigned_to = u1.id
                LEFT JOIN users u2 ON t.created_by = u2.id
                LEFT JOIN projects p ON t.project_id = p.id
                ORDER BY t.created_at DESC
            """)
    else:
        if project_id:
            cursor.execute("""
                SELECT t.*,
                       u1.name as assigned_to_name,
                       u2.name as created_by_name,
                       p.name as project_name
                FROM tasks t
                LEFT JOIN users u1 ON t.assigned_to = u1.id
                LEFT JOIN users u2 ON t.created_by = u2.id
                LEFT JOIN projects p ON t.project_id = p.id
                JOIN project_members pm ON pm.project_id = t.project_id
                WHERE t.project_id = %s AND pm.user_id = %s
                ORDER BY t.created_at DESC
            """, (project_id, current_user["id"]))
        else:
            cursor.execute("""
                SELECT t.*,
                       u1.name as assigned_to_name,
                       u2.name as created_by_name,
                       p.name as project_name
                FROM tasks t
                LEFT JOIN users u1 ON t.assigned_to = u1.id
                LEFT JOIN users u2 ON t.created_by = u2.id
                LEFT JOIN projects p ON t.project_id = p.id
                JOIN project_members pm ON pm.project_id = t.project_id
                WHERE pm.user_id = %s
                ORDER BY t.created_at DESC
            """, (current_user["id"],))

    tasks = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convert date objects to string for JSON
    for task in tasks:
        if task.get("due_date"):
            task["due_date"] = str(task["due_date"])
        if task.get("created_at"):
            task["created_at"] = str(task["created_at"])
        if task.get("updated_at"):
            task["updated_at"] = str(task["updated_at"])

    return tasks


# Get single task by ID
@router.get("/{task_id}")
def get_task(task_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = get_cursor(conn)

    cursor.execute("""
        SELECT t.*,
               u1.name as assigned_to_name,
               u2.name as created_by_name,
               p.name as project_name
        FROM tasks t
        LEFT JOIN users u1 ON t.assigned_to = u1.id
        LEFT JOIN users u2 ON t.created_by = u2.id
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.id = %s
    """, (task_id,))
    task = cursor.fetchone()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check project access for members
    if current_user["role"] != "admin":
        cursor.execute(
            "SELECT id FROM project_members WHERE project_id = %s AND user_id = %s",
            (task["project_id"], current_user["id"])
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Access denied")

    # Convert dates
    if task.get("due_date"):
        task["due_date"] = str(task["due_date"])
    if task.get("created_at"):
        task["created_at"] = str(task["created_at"])
    if task.get("updated_at"):
        task["updated_at"] = str(task["updated_at"])

    cursor.close()
    conn.close()
    return task


# Update task status or details
@router.patch("/{task_id}")
def update_task(task_id: int, data: TaskUpdate, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = get_cursor(conn)

    cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
    task = cursor.fetchone()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Members can only update status of tasks assigned to them
    if current_user["role"] != "admin":
        if task["assigned_to"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="You can only update tasks assigned to you")

        # Members can only change status, nothing else
        allowed_fields = {"status"}
        provided_fields = {k for k, v in data.model_dump().items() if v is not None}
        if not provided_fields.issubset(allowed_fields):
            raise HTTPException(status_code=403, detail="Members can only update task status")

    # Validate status value
    if data.status and data.status not in ["todo", "in_progress", "done"]:
        raise HTTPException(status_code=400, detail="Status must be todo, in_progress, or done")

    if data.priority and data.priority not in ["low", "medium", "high"]:
        raise HTTPException(status_code=400, detail="Priority must be low, medium, or high")

    # Build dynamic update query
    fields = []
    values = []

    if data.title is not None:
        fields.append("title = %s")
        values.append(data.title)
    if data.description is not None:
        fields.append("description = %s")
        values.append(data.description)
    if data.status is not None:
        fields.append("status = %s")
        values.append(data.status)
    if data.priority is not None:
        fields.append("priority = %s")
        values.append(data.priority)
    if data.due_date is not None:
        fields.append("due_date = %s")
        values.append(data.due_date)
    if data.assigned_to is not None:
        fields.append("assigned_to = %s")
        values.append(data.assigned_to)

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(task_id)
    cursor.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = %s", values)
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Task updated successfully"}


# Delete task (Admin only)
@router.delete("/{task_id}")
def delete_task(task_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete tasks")

    conn = get_connection()
    cursor = get_cursor(conn)

    cursor.execute("SELECT id FROM tasks WHERE id = %s", (task_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Task not found")

    cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Task deleted"}


# Get overdue tasks
@router.get("/filter/overdue")
def get_overdue_tasks(current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = get_cursor(conn)

    if current_user["role"] == "admin":
        cursor.execute("""
            SELECT t.*,
                   u1.name as assigned_to_name,
                   p.name as project_name
            FROM tasks t
            LEFT JOIN users u1 ON t.assigned_to = u1.id
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.due_date < CURDATE() AND t.status != 'done'
            ORDER BY t.due_date ASC
        """)
    else:
        cursor.execute("""
            SELECT t.*,
                   u1.name as assigned_to_name,
                   p.name as project_name
            FROM tasks t
            LEFT JOIN users u1 ON t.assigned_to = u1.id
            LEFT JOIN projects p ON t.project_id = p.id
            JOIN project_members pm ON pm.project_id = t.project_id
            WHERE t.due_date < CURDATE()
              AND t.status != 'done'
              AND pm.user_id = %s
            ORDER BY t.due_date ASC
        """, (current_user["id"],))

    tasks = cursor.fetchall()
    cursor.close()
    conn.close()

    for task in tasks:
        if task.get("due_date"):
            task["due_date"] = str(task["due_date"])
        if task.get("created_at"):
            task["created_at"] = str(task["created_at"])

    return tasks


# Dashboard stats
@router.get("/filter/dashboard")
def get_dashboard(current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = get_cursor(conn)

    if current_user["role"] == "admin":
        cursor.execute("SELECT COUNT(*) as total FROM tasks")
        total = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'todo'")
        todo = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'in_progress'")
        in_progress = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'done'")
        done = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE due_date < CURDATE() AND status != 'done'")
        overdue = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM projects")
        total_projects = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()["count"]

    else:
        cursor.execute("""
            SELECT COUNT(*) as total FROM tasks t
            JOIN project_members pm ON pm.project_id = t.project_id
            WHERE pm.user_id = %s
        """, (current_user["id"],))
        total = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) as count FROM tasks t
            JOIN project_members pm ON pm.project_id = t.project_id
            WHERE pm.user_id = %s AND t.status = 'todo'
        """, (current_user["id"],))
        todo = cursor.fetchone()["count"]

        cursor.execute("""
            SELECT COUNT(*) as count FROM tasks t
            JOIN project_members pm ON pm.project_id = t.project_id
            WHERE pm.user_id = %s AND t.status = 'in_progress'
        """, (current_user["id"],))
        in_progress = cursor.fetchone()["count"]

        cursor.execute("""
            SELECT COUNT(*) as count FROM tasks t
            JOIN project_members pm ON pm.project_id = t.project_id
            WHERE pm.user_id = %s AND t.status = 'done'
        """, (current_user["id"],))
        done = cursor.fetchone()["count"]

        cursor.execute("""
            SELECT COUNT(*) as count FROM tasks t
            JOIN project_members pm ON pm.project_id = t.project_id
            WHERE pm.user_id = %s AND t.due_date < CURDATE() AND t.status != 'done'
        """, (current_user["id"],))
        overdue = cursor.fetchone()["count"]

        cursor.execute("""
            SELECT COUNT(*) as count FROM project_members
            WHERE user_id = %s
        """, (current_user["id"],))
        total_projects = cursor.fetchone()["count"]

        total_users = None

    cursor.close()
    conn.close()

    return {
        "total_tasks": total,
        "todo": todo,
        "in_progress": in_progress,
        "done": done,
        "overdue": overdue,
        "total_projects": total_projects,
        "total_users": total_users
    }