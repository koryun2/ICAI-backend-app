from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.views import TokenObtainPairView
import secrets

from django.conf import settings
from django.db import transaction
from django.db.models import Max
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
from .models import InterviewSession, InterviewQuestion
from .serializers import (
    InterviewSessionCreateSerializer,
    InterviewSessionListSerializer,
    InterviewSessionDetailSerializer,
    InterviewAnswerSerializer,
    InterviewGenerateSerializer,
    InterviewQuestionSerializer,
)


def can_access_session(session, request, token_from_request: str | None):
    """
    Single source of truth for session access permissions.
    
    Returns True if access is allowed, raises PermissionDenied otherwise.
    Uses timing-safe comparison for token validation.
    """
    # Owner access
    if session.user_id and request.user.is_authenticated and session.user_id == request.user.id:
        return True

    # Guest access (token required)
    if session.user_id is None:
        if token_from_request and secrets.compare_digest(token_from_request, session.public_token):
            return True
        raise PermissionDenied("Guest token required or invalid.")

    raise PermissionDenied("Forbidden.")


class InterviewSessionListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return InterviewSession.objects.filter(user=self.request.user).order_by("-created_at")
        return InterviewSession.objects.none()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return InterviewSessionCreateSerializer
        return InterviewSessionListSerializer

    def create(self, request, *args, **kwargs):
        create_ser = InterviewSessionCreateSerializer(data=request.data)
        create_ser.is_valid(raise_exception=True)

        generate_path = getattr(settings, "FASTAPI_INTERVIEW_GENERATE_PATH", "/api/v1/interviews/generate")
        default_question_count = getattr(settings, "FASTAPI_DEFAULT_QUESTION_COUNT", 5)

        with transaction.atomic():
            user = request.user if request.user.is_authenticated else None
            session = create_ser.save(user=user, status=InterviewSession.Status.CREATED)

            profile = {
                "role": session.role,
                "position": session.position,
                "level": session.level,
                "stack": session.tech_stack,
            }

            payload = {
                "fastapi_session_id": None,
                "profile": profile,
                "count": default_question_count,
                "existing_questions": [],
            }

            try:
                fastapi_resp = call_interview_engine(generate_path, payload)
            except Exception as e:
                session.status = InterviewSession.Status.FAILED
                session.save(update_fields=["status", "updated_at"])
                return Response({"detail": f"Failed to generate questions: {e}"}, status=status.HTTP_502_BAD_GATEWAY)

            session.fastapi_session_id = fastapi_resp.get("fastapi_session_id", "") or ""
            session.status = InterviewSession.Status.IN_PROGRESS
            session.started_at = timezone.now()
            session.save(update_fields=["status", "started_at", "fastapi_session_id", "updated_at"])

            questions_list = [q.strip() for q in fastapi_resp.get("questions", []) if q and q.strip()]

            for idx, qtext in enumerate(questions_list, start=1):
                InterviewQuestion.objects.create(session=session, order=idx, question=qtext)

        session = InterviewSession.objects.filter(id=session.id).prefetch_related("questions").first()
        detail = InterviewSessionDetailSerializer(session).data
        
        if session.user is None:
            detail["public_token"] = session.public_token
        
        return Response(detail, status=status.HTTP_201_CREATED)


class InterviewSessionDetailView(generics.RetrieveAPIView):
    """
    GET /api/interviews/<uuid:id>/ -> full session details with questions
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = InterviewSessionDetailSerializer
    lookup_field = "id"
    lookup_url_kwarg = "session_id"

    def get_queryset(self):
        return InterviewSession.objects.all().prefetch_related("questions")

    def get_object(self):
        session = super().get_object()
        token = self.request.headers.get("X-Interview-Token")
        can_access_session(session, self.request, token)
        return session


class InterviewAnswerView(APIView):
    """
    POST /api/interviews/<uuid:session_id>/answer/
    Body: {"question_id": "...", "answer": "...", "check_only": false}
    -> Django sends to FastAPI /check, stores feedback.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, session_id):
        ans_ser = InterviewAnswerSerializer(data=request.data)
        ans_ser.is_valid(raise_exception=True)
        question_id = ans_ser.validated_data["question_id"]
        answer = ans_ser.validated_data["answer"]
        check_only = ans_ser.validated_data.get("check_only", False)

        with transaction.atomic():
            session = InterviewSession.objects.select_for_update().get(id=session_id)
            # Re-check access inside the transaction
            token = request.headers.get("X-Interview-Token")
            can_access_session(session, request, token)

            question = get_object_or_404(
                InterviewQuestion,
                id=question_id,
                session=session
            )
            question.answer = answer
            question.answered_at = timezone.now()
            question.save(update_fields=["answer", "answered_at"])

            check_path = getattr(settings, "FASTAPI_INTERVIEW_CHECK_PATH", "/api/v1/interviews/check")

            payload = {
                "fastapi_session_id": session.fastapi_session_id,
                "question": question.question,
                "answer": answer,
                "context": {
                    "role": session.role,
                    "position": session.position,
                    "level": session.level,
                    "stack": session.tech_stack,
                },
            }

            try:
                fastapi_resp = call_interview_engine(check_path, payload)
            except Exception as e:
                return Response(
                    {"detail": f"Failed to evaluate answer in FastAPI: {e}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            # Store per-question feedback
            question.feedback = fastapi_resp.get("feedback", "") or ""
            question.score = fastapi_resp.get("score", None)
            question.meta = fastapi_resp.get("meta", {}) or {}
            question.save(update_fields=["feedback", "score", "meta"])

            # Handle overall feedback if provided (for interview completion)
            # Only complete session if not check_only
            overall_feedback = fastapi_resp.get("overall_feedback")
            overall_score = fastapi_resp.get("overall_score")
            overall_meta = fastapi_resp.get("overall_meta")

            if not check_only and (overall_feedback is not None or overall_score is not None):
                if overall_feedback is not None:
                    session.overall_feedback = overall_feedback
                if overall_score is not None:
                    session.overall_score = overall_score
                if overall_meta is not None:
                    session.overall_meta = overall_meta
                session.status = InterviewSession.Status.COMPLETED
                session.ended_at = session.ended_at or timezone.now()
                session.save()

        session = InterviewSession.objects.filter(id=session.id).prefetch_related("questions").first()
        detail = InterviewSessionDetailSerializer(session).data
        return Response(detail, status=status.HTTP_200_OK)


class InterviewGenerateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, session_id):
        session = get_object_or_404(InterviewSession, id=session_id)
        token = request.headers.get("X-Interview-Token")
        can_access_session(session, request, token)

        gen_ser = InterviewGenerateSerializer(data=request.data)
        gen_ser.is_valid(raise_exception=True)
        count = gen_ser.validated_data["count"]

        generate_path = getattr(settings, "FASTAPI_INTERVIEW_GENERATE_PATH", "/api/v1/interviews/generate")

        with transaction.atomic():
            session = InterviewSession.objects.select_for_update().get(id=session_id)

            existing_questions = list(session.questions.values_list("question", flat=True))
            existing_set = set(existing_questions)

            max_order = session.questions.aggregate(Max("order"))["order__max"] or 0
            next_order = max_order + 1

            profile = {
                "role": session.role,
                "position": session.position,
                "level": session.level,
                "stack": session.tech_stack,
            }

            payload = {
                "fastapi_session_id": session.fastapi_session_id or None,
                "profile": profile,
                "count": count,
                "existing_questions": existing_questions,
            }

            try:
                fastapi_resp = call_interview_engine(generate_path, payload)
            except Exception as e:
                return Response({"detail": f"Failed to generate questions: {e}"}, status=status.HTTP_502_BAD_GATEWAY)

            if fastapi_resp.get("fastapi_session_id") and not session.fastapi_session_id:
                session.fastapi_session_id = fastapi_resp["fastapi_session_id"]

            questions_list = [q.strip() for q in fastapi_resp.get("questions", []) if q and q.strip()]
            questions_list = [q for q in questions_list if q not in existing_set]

            for i, qtext in enumerate(questions_list):
                InterviewQuestion.objects.create(session=session, order=next_order + i, question=qtext)

            session.status = InterviewSession.Status.IN_PROGRESS
            session.save(update_fields=["status", "fastapi_session_id", "updated_at"])

        session = InterviewSession.objects.filter(id=session_id).prefetch_related("questions").first()
        return Response(InterviewSessionDetailSerializer(session).data, status=status.HTTP_200_OK)
