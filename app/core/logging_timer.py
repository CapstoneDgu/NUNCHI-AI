import logging
import time
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


@contextmanager
def log_step(
        step: str,
        request_id: Optional[str] = None,
        **extra,
):
    start = time.perf_counter()

    try:
        yield
    except Exception:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        extra_text = " ".join(f"{key}={value}" for key, value in extra.items())

        message = (
            f"[AI_STEP] requestId={request_id} "
            f"step={step} elapsedMs={elapsed_ms} "
            f"status=FAIL {extra_text}"
        )

        print(message, flush=True)
        logger.exception(message)
        raise

    else:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        extra_text = " ".join(f"{key}={value}" for key, value in extra.items())

        message = (
            f"[AI_STEP] requestId={request_id} "
            f"step={step} elapsedMs={elapsed_ms} "
            f"status=SUCCESS {extra_text}"
        )

        print(message, flush=True)
        logger.info(message)