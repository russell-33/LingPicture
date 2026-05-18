import hmac
from typing import Optional

from fastapi import Request

from src.config import settings

INTERNAL_TOKEN_HEADER = "X-Internal-Token"
INTERNAL_USER_HEADER = "X-Internal-User-Id"


def validate_internal_request(request: Request) -> bool:
    actual = request.headers.get(INTERNAL_TOKEN_HEADER, "")
    expected = settings.ai_internal_token
    return bool(expected) and hmac.compare_digest(actual, expected)


def internal_headers(user_id: Optional[int] = None) -> dict[str, str]:
    headers = {INTERNAL_TOKEN_HEADER: settings.ai_internal_token}
    if user_id is not None:
        headers[INTERNAL_USER_HEADER] = str(user_id)
    return headers
