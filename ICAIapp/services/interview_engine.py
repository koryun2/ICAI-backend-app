import json

import httpx
from django.conf import settings


class InterviewEngineError(Exception):
    def __init__(self, detail: str, status_code: int = 502):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def generate_questions(payload: dict, timeout: int = 20) -> dict:
    path = getattr(settings, "FASTAPI_GENERATE_PATH", "/api/v1/interviews/generate")
    return _post(path, payload, timeout=timeout)


def evaluate_interview(payload: dict, timeout: int = 30) -> dict:
    path = getattr(settings, "FASTAPI_EVALUATE_PATH", "/api/v1/interviews/evaluate")
    return _post(path, payload, timeout=timeout)


def _post(path: str, payload: dict, timeout: int) -> dict:
    base = settings.FASTAPI_BASE_URL.rstrip("/")
    url = f"{base}{path}"

    try:
        response = httpx.post(url, json=payload, timeout=timeout)
    except httpx.RequestError as exc:
        raise InterviewEngineError(f"Network error contacting interview engine: {exc}") from exc

    if response.status_code < 200 or response.status_code >= 300:
        body = response.text.strip()
        if response.status_code == 400:
            raise InterviewEngineError(
                body or "Bad request to interview engine.", status_code=400
            )
        if response.status_code >= 500:
            raise InterviewEngineError(
                f"Interview engine error {response.status_code}: {body}",
                status_code=502,
            )
        raise InterviewEngineError(
            f"Interview engine error {response.status_code}: {body}",
            status_code=502,
        )

    try:
        return response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise InterviewEngineError("Invalid JSON received from interview engine.") from exc
