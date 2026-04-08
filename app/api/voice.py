from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("")
async def process_voice() -> dict:
    """음성 처리 API (골격)"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="음성 처리 API는 아직 구현 전입니다.",
    )
