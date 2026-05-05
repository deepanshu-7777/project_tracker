from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from backend.routes import auth, projects, tasks

security = HTTPBearer()

app = FastAPI(
    title="Project Tracker API",
    version="1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/api/auth",     tags=["Auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(tasks.router,    prefix="/api/tasks",    tags=["Tasks"])

@app.get("/health")
def health():
    return {"status": "ok"}