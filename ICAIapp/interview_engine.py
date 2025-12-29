import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.utils import timezone


def call_interview_engine(path: str, payload: dict, timeout: int = 20) -> dict:
    """
    Single entry point for all interview-engine calls.
    Switches between mock and real FastAPI automatically.
    """
    if getattr(settings, "FASTAPI_MOCK", False):
        return _mock_response(path, payload)

    return _real_fastapi_call(path, payload, timeout)


# ─────────────────────────────────────────────
# REAL FastAPI
# ─────────────────────────────────────────────

def _real_fastapi_call(path: str, payload: dict, timeout: int) -> dict:
    base = settings.FASTAPI_BASE_URL.rstrip("/")
    url = base + path

    data = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8").strip()
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
        raise RuntimeError(f"FastAPI HTTPError {e.code}: {body}")
    except URLError as e:
        raise RuntimeError(f"FastAPI URLError: {e}")


# ─────────────────────────────────────────────
# MOCK FastAPI (PERMANENT)
# ─────────────────────────────────────────────

def _mock_response(path: str, payload: dict) -> dict:
    """
    Permanent mock. Must ALWAYS mirror real FastAPI response shape.
    """

    # Interview start
    if "start" in path:
        return {
            "fastapi_session_id": "mock-session-001",
            "question": "Explain how Django ORM works internally."
        }

    # Interview answer
    if "answer" in path:
        turn = payload.get("turn", 1)

        if turn < 3:
            return {
                "feedback": f"Mock feedback for question {turn}",
                "score": 7,
                "next_question": f"Mock question {turn + 1}",
                "done": False,
            }

        return {
            "feedback": "Final mock feedback",
            "score": 8,
            "done": True,
            "overall_feedback": "Strong interview performance (mock).",
            "overall_score": 8,
            "overall_meta": {
                "strengths": ["Python", "Django"],
                "gaps": ["System design"]
            },
        }

    return {}
