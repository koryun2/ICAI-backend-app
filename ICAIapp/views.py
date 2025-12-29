from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from .interview_engine import call_interview_engine

from .serializers import RegisterSerializer, UserSerializer, MeUpdateSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class LoginView(TokenObtainPairView):
    # With your custom User model (USERNAME_FIELD="email"),
    # this endpoint expects: {"email": "...", "password": "..."}
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return MeUpdateSerializer
        return UserSerializer
from .models import InterviewSession, InterviewTurn
from .serializers import (
    InterviewSessionCreateSerializer,
    InterviewSessionListSerializer,
    InterviewSessionDetailSerializer,
    InterviewAnswerSerializer,
    InterviewTurnSerializer,
)

# def _fastapi_post_json(path: str, payload: dict, timeout: int = 20) -> dict:
#     """
#     POST JSON to FastAPI and parse JSON response.
#     Raise a DRF-friendly exception upstream if FastAPI fails.
#     """
#     base = settings.FASTAPI_BASE_URL.rstrip("/")
#     url = base + path

#     data = json.dumps(payload).encode("utf-8")
#     req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

#     try:
#         with urlopen(req, timeout=timeout) as resp:
#             raw = resp.read().decode("utf-8").strip()
#             return json.loads(raw) if raw else {}
#     except HTTPError as e:
#         body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
#         raise RuntimeError(f"FastAPI HTTPError {e.code}: {body}")
#     except URLError as e:
#         raise RuntimeError(f"FastAPI URLError: {e}")


class InterviewSessionListCreateView(generics.ListAPIView):
    """
    GET  /api/interviews/  -> history list
    POST /api/interviews/  -> create session + ask FastAPI for first question
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return InterviewSession.objects.filter(user=self.request.user).order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return InterviewSessionCreateSerializer
        return InterviewSessionListSerializer

    def post(self, request, *args, **kwargs):
        create_ser = InterviewSessionCreateSerializer(data=request.data)
        create_ser.is_valid(raise_exception=True)

        # You can configure these in settings later if you want:
        start_path = getattr(settings, "FASTAPI_INTERVIEW_START_PATH", "/api/v1/interviews/start")

        with transaction.atomic():
            session = create_ser.save(user=request.user, status=InterviewSession.Status.CREATED)

            payload = {
                "session_id": str(session.id),
                "role": session.role,
                "position": session.position,
                "level": session.level,
                "stack": session.tech_stack,
                "user_id": session.user_id,
            }

            try:
                fastapi_resp = call_interview_engine(start_path, payload)
            except Exception as e:
                session.status = InterviewSession.Status.FAILED
                session.save(update_fields=["status", "updated_at"])
                return Response(
                    {"detail": f"Failed to start interview in FastAPI: {e}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            first_question = fastapi_resp.get("question") or fastapi_resp.get("first_question")
            session.fastapi_session_id = fastapi_resp.get("fastapi_session_id", "") or fastapi_resp.get("thread_id", "")

            session.status = InterviewSession.Status.IN_PROGRESS
            session.started_at = session.started_at or timezone.now()
            session.save(update_fields=["status", "started_at", "fastapi_session_id", "updated_at"])

            if first_question:
                InterviewTurn.objects.create(session=session, order=1, question=first_question)

        detail = InterviewSessionDetailSerializer(session).data
        return Response(detail, status=status.HTTP_201_CREATED)


class InterviewSessionDetailView(generics.RetrieveAPIView):
    """
    GET /api/interviews/<uuid:id>/ -> full session details with turns
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InterviewSessionDetailSerializer
    lookup_field = "id"
    lookup_url_kwarg = "session_id"

    def get_queryset(self):
        return InterviewSession.objects.filter(user=self.request.user).prefetch_related("turns")


class InterviewAnswerView(APIView):
    """
    POST /api/interviews/<uuid:id>/answer/
    Body: {"answer": "..."}
    -> Django sends to FastAPI, stores feedback, creates next question if provided.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(InterviewSession, id=session_id, user=request.user)

        ans_ser = InterviewAnswerSerializer(data=request.data)
        ans_ser.is_valid(raise_exception=True)
        answer = ans_ser.validated_data["answer"]

        # Find latest unanswered turn
        turn = session.turns.filter(answer="").order_by("-order").first()
        if not turn:
            return Response(
                {"detail": "No pending question to answer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        turn.answer = answer
        turn.answered_at = timezone.now()
        turn.save(update_fields=["answer", "answered_at"])

        answer_path = getattr(settings, "FASTAPI_INTERVIEW_ANSWER_PATH", "/api/v1/interviews/answer")

        payload = {
            "session_id": str(session.id),
            "fastapi_session_id": session.fastapi_session_id,
            "turn": turn.order,
            "question": turn.question,
            "answer": answer,
        }

        try:
            fastapi_resp = call_interview_engine(answer_path, payload)
        except Exception as e:
            return Response(
                {"detail": f"Failed to evaluate answer in FastAPI: {e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Store per-question feedback
        turn.feedback = fastapi_resp.get("feedback", "") or ""
        turn.score = fastapi_resp.get("score", None)
        turn.meta = fastapi_resp.get("meta", {}) or {}
        turn.save(update_fields=["feedback", "score", "meta"])

        # Next question or completion
        next_q = fastapi_resp.get("next_question")
        done = bool(fastapi_resp.get("done"))

        if next_q:
            InterviewTurn.objects.create(session=session, order=turn.order + 1, question=next_q)

        overall_feedback = fastapi_resp.get("overall_feedback")
        overall_score = fastapi_resp.get("overall_score")
        overall_meta = fastapi_resp.get("overall_meta")

        if done or overall_feedback:
            session.status = InterviewSession.Status.COMPLETED
            session.ended_at = session.ended_at or timezone.now()
            if overall_feedback is not None:
                session.overall_feedback = overall_feedback
            if overall_score is not None:
                session.overall_score = overall_score
            if overall_meta is not None:
                session.overall_meta = overall_meta
        else:
            session.status = InterviewSession.Status.IN_PROGRESS

        session.save()

        return Response(
            {
                "turn": InterviewTurnSerializer(turn).data,
                "next_question": next_q,
                "session_status": session.status,
                "overall_feedback": session.overall_feedback,
            },
            status=status.HTTP_200_OK,
        )
