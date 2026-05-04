from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
def tasks_test():
    return {"message": "Tasks route working"}