from fastapi import APIRouter

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("")
async def process_voice() -> dict:
    """음성 처리 API (골격)"""
    raise NotImplementedError
