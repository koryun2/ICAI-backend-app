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

    # Generate questions endpoint (used for both initial + generate more)
    if "generate" in path:
        count = payload.get("count", 5)
        fastapi_session_id = payload.get("fastapi_session_id") or "mock-session-001"
        existing_questions = payload.get("existing_questions", [])
        profile = payload.get("profile", {})
        role = profile.get("role", "software development")
        level = profile.get("level", "")
        stack = profile.get("stack", [])
        
        # Generate unique questions that aren't duplicates
        base_questions = [
            f"Explain how {role} works in production environments.",
            f"Describe the architecture patterns used in {role} development.",
            f"What are the key challenges in {role}?",
            f"How do you handle state management in {role}?",
            f"What testing strategies do you use for {role}?",
            f"Explain performance optimization in {role}.",
            f"Describe security best practices for {role}.",
            f"How do you handle scalability in {role} applications?",
            f"What are the latest trends in {role}?",
            f"Explain deployment strategies for {role} applications.",
        ]
        
        if stack:
            for tech in stack[:3]:  # Use first 3 techs
                base_questions.extend([
                    f"How do you use {tech} in {role}?",
                    f"What are the advantages of {tech} for {role}?",
                ])
        
        if level:
            base_questions.append(f"As a {level} {role} developer, how do you approach code reviews?")
        
        available_questions = [q for q in base_questions if q not in existing_questions]
        
        questions = []
        question_num = len(existing_questions) + 1
        while len(questions) < count:
            if available_questions:
                questions.append(available_questions.pop(0))
            else:
                questions.append(f"Mock question {question_num}: Explain {role} concepts in detail.")
                question_num += 1
        
        return {
            "fastapi_session_id": fastapi_session_id,
            "questions": questions[:count],
        }

    # Check answer endpoint
    if "check" in path:
        question = payload.get("question", "")
        answer = payload.get("answer", "")
        
        # Simple mock scoring
        score = min(10, max(1, len(answer) // 20))
        
        return {
            "feedback": f"Mock feedback: Your answer about '{question[:50]}...' shows understanding. Score: {score}/10",
            "score": score,
            "meta": {
                "length": len(answer),
                "has_code": "def" in answer.lower() or "class" in answer.lower(),
            },
        }

    return {}
