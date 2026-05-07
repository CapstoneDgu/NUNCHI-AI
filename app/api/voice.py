from fastapi import APIRouter, status

from domain.api_response import ApiErrorResponse

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post(
    "",
    response_model=ApiErrorResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="음성 주문 처리",
    description=(
        "음성 입력 기반 주문 처리 엔드포인트입니다.\n\n"
        "현재는 스켈레톤만 정의되어 있으며 실제 STT/TTS 또는 음성 대화 처리 로직은 아직 구현되지 않았습니다. "
        "호출 시 항상 `501 Not Implemented`를 반환합니다."
    ),
    responses={
        501: {
            "model": ApiErrorResponse,
            "description": "아직 구현되지 않은 API입니다.",
        }
    },
)
async def process_voice() -> ApiErrorResponse:
    """음성 처리 API (골격)"""
    return ApiErrorResponse(
        code="VOICE_NOT_IMPLEMENTED",
        message="음성 처리 API는 아직 구현 전입니다.",
    )
