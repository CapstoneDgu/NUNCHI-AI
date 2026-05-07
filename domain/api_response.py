from pydantic import BaseModel, ConfigDict, Field


class ApiErrorResponse(BaseModel):
    """공통 오류 응답 모델"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "SPRING_API_ERROR",
                "message": "주문 세션을 생성하지 못했습니다.",
            }
        }
    )

    code: str = Field(
        description="애플리케이션에서 정의한 오류 코드입니다.",
        examples=["SPRING_API_ERROR", "SPRING_TIMEOUT", "KIOSK_ERROR"],
    )
    message: str = Field(
        description="클라이언트 또는 사용자에게 전달할 오류 메시지입니다.",
        examples=["Spring API 응답 시간 초과"],
    )


class HealthCheckResponse(BaseModel):
    """헬스 체크 응답 모델"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
            }
        }
    )

    status: str = Field(
        description="서버 상태입니다. 정상 동작 중이면 `ok`를 반환합니다.",
        examples=["ok"],
    )
