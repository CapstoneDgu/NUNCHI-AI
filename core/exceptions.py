class KioskError(Exception):
    """NUNCHI 키오스크 공통 베이스 예외"""

    def __init__(self, message: str, code: str = "KIOSK_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


# Spring 연동 예외
class SpringApiError(KioskError):
    """Spring API 비정상 응답"""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.status_code = status_code
        super().__init__(message, code="SPRING_API_ERROR")


class SpringApiTimeoutError(KioskError):
    """Spring API 타임아웃"""

    def __init__(self) -> None:
        super().__init__("Spring API 응답 시간 초과", code="SPRING_TIMEOUT")


# 주문/결제 예외
class OrderNotConfirmedError(KioskError):
    """주문 확정 전 결제 시도"""

    def __init__(self) -> None:
        super().__init__("주문이 확정되지 않았습니다", code="ORDER_NOT_CONFIRMED")


class PaymentAlreadyExistsError(KioskError):
    """중복 결제 시도"""

    def __init__(self) -> None:
        super().__init__("이미 결제가 진행 중입니다", code="PAYMENT_ALREADY_EXISTS")


# 음성 처리 예외
class SttError(KioskError):
    """STT 변환 실패"""

    def __init__(self, message: str = "음성 인식에 실패했습니다") -> None:
        super().__init__(message, code="STT_ERROR")


class TtsError(KioskError):
    """TTS 합성 실패"""

    def __init__(self, message: str = "음성 합성에 실패했습니다") -> None:
        super().__init__(message, code="TTS_ERROR")


# 에이전트 예외
class AgentLoopLimitError(KioskError):
    """LLM 에이전트 루프 횟수 초과"""

    def __init__(self) -> None:
        super().__init__("에이전트 처리 한도를 초과했습니다", code="AGENT_LOOP_LIMIT")
