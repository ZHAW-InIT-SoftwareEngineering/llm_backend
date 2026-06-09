from fastapi import APIRouter

router = APIRouter()

@router.post("/chat", status_code=200)
def chat() -> dict[str, str]:
    return {"status": "ok"}