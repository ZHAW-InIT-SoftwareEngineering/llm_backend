from fastapi import APIRouter
from api.schemas.healthz.healthz import HealthzResponse

router = APIRouter()

@router.get("/healthz", response_model=HealthzResponse, status_code=200)
def healthz() -> HealthzResponse:
    return HealthzResponse(status="ok")
