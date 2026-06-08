from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz", status_code=200)
def healthz() -> dict[str, str]:
    return {"status": "ok"}
