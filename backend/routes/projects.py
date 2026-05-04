from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
def projects_test():
    return {"message": "Projects route working"}