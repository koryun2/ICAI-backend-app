from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import InterviewSession, InterviewTurn
from .serializers import (
    InterviewEvaluateSerializer,
    InterviewGenerateSerializer,
    InterviewQuestionUpdateSerializer,
    InterviewSessionCreateSerializer,
    InterviewSessionDetailSerializer,
    InterviewSessionListSerializer,
    InterviewTurnSerializer,
    MeUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .services.interview_engine import InterviewEngineError, evaluate_interview, generate_questions


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


def can_access_session(session: InterviewSession, request) -> None:
    if session.user_id:
        if not request.user.is_authenticated or session.user_id != request.user.id:
            raise PermissionDenied("You do not have access to this interview session.")
        return

    token = request.headers.get("X-Interview-Token") or request.query_params.get("t")
    if not token or token != session.public_token:
        raise PermissionDenied("Missing or invalid interview token.")


class InterviewSessionListCreateView(APIView):
    """
    GET  /api/interviews/  -> history list (authenticated only)
    POST /api/interviews/  -> create session + generate initial questions
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        sessions = InterviewSession.objects.filter(user=request.user).order_by("-created_at")
        serializer = InterviewSessionListSerializer(sessions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        create_ser = InterviewSessionCreateSerializer(data=request.data)
        create_ser.is_valid(raise_exception=True)

        question_count = create_ser.validated_data.pop("count", None)
        question_count = question_count or getattr(
            settings, "FASTAPI_DEFAULT_QUESTION_COUNT", 5
        )

        with transaction.atomic():
            session = create_ser.save(
                user=request.user if request.user.is_authenticated else None,
                status=InterviewSession.Status.CREATED,
            )

            profile = {
                "role": session.role,
                "level": session.level,
                "stack": session.tech_stack,
                "mode": session.mode,
            }

            payload = {
                "fastapi_session_id": None,
                "profile": profile,
                "count": question_count,
                "existing_questions": [],
            }

            try:
                fastapi_resp = generate_questions(payload)
            except InterviewEngineError as exc:
                session.status = InterviewSession.Status.FAILED
                session.save(update_fields=["status", "updated_at"])
                return Response({"detail": exc.detail}, status=exc.status_code)

            questions = [q.strip() for q in fastapi_resp.get("questions", []) if q and q.strip()]
            if not questions:
                session.status = InterviewSession.Status.FAILED
                session.save(update_fields=["status", "updated_at"])
                return Response(
                    {"detail": "Interview engine returned no questions."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            session.fastapi_session_id = fastapi_resp.get("fastapi_session_id", "") or ""
            session.status = InterviewSession.Status.IN_PROGRESS
            session.started_at = session.started_at or timezone.now()
            session.save(update_fields=["status", "started_at", "fastapi_session_id", "updated_at"])

            InterviewTurn.objects.bulk_create(
                [
                    InterviewTurn(session=session, order=index + 1, question=question)
                    for index, question in enumerate(questions)
                ]
            )

        detail = InterviewSessionDetailSerializer(session).data
        if session.user_id is None:
            detail["public_token"] = session.public_token
        return Response(detail, status=status.HTTP_201_CREATED)


class InterviewSessionDetailView(APIView):
    """
    GET /api/interviews/<uuid:session_id>/ -> full session details with questions
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, session_id):
        session = get_object_or_404(
            InterviewSession.objects.prefetch_related("turns"), id=session_id
        )
        can_access_session(session, request)
        return Response(
            InterviewSessionDetailSerializer(session).data, status=status.HTTP_200_OK
        )


class InterviewGenerateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, session_id):
        gen_ser = InterviewGenerateSerializer(data=request.data)
        gen_ser.is_valid(raise_exception=True)
        count = gen_ser.validated_data["count"]
        max_count = getattr(settings, "FASTAPI_MAX_GENERATE_COUNT", 50)
        count = min(count, max_count)

        with transaction.atomic():
            session = get_object_or_404(
                InterviewSession.objects.select_for_update(), id=session_id
            )
            can_access_session(session, request)

            existing_questions = list(session.turns.values_list("question", flat=True))
            existing_set = {
                question.strip().lower()
                for question in existing_questions
                if question and question.strip()
            }

            max_order = session.turns.aggregate(Max("order"))["order__max"] or 0
            next_order = max_order + 1

            profile = {
                "role": session.role,
                "level": session.level,
                "stack": session.tech_stack,
                "mode": session.mode,
            }

            payload = {
                "fastapi_session_id": session.fastapi_session_id or None,
                "profile": profile,
                "count": count,
                "existing_questions": existing_questions,
            }

            try:
                fastapi_resp = generate_questions(payload)
            except InterviewEngineError as exc:
                return Response({"detail": exc.detail}, status=exc.status_code)

            if fastapi_resp.get("fastapi_session_id") and not session.fastapi_session_id:
                session.fastapi_session_id = fastapi_resp["fastapi_session_id"]

            questions_list = [
                q.strip() for q in fastapi_resp.get("questions", []) if q and q.strip()
            ]
            questions_list = [
                q for q in questions_list if q.strip().lower() not in existing_set
            ]

            if not questions_list:
                return Response(
                    {"detail": "No new questions generated."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            InterviewTurn.objects.bulk_create(
                [
                    InterviewTurn(session=session, order=next_order + i, question=question)
                    for i, question in enumerate(questions_list)
                ]
            )

            session.status = InterviewSession.Status.IN_PROGRESS
            session.save(update_fields=["status", "fastapi_session_id", "updated_at"])

        session = InterviewSession.objects.prefetch_related("turns").get(id=session_id)
        return Response(InterviewSessionDetailSerializer(session).data, status=status.HTTP_200_OK)


class InterviewQuestionDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def patch(self, request, session_id, order):
        session = get_object_or_404(InterviewSession, id=session_id)
        can_access_session(session, request)
        turn = get_object_or_404(InterviewTurn, session=session, order=order)

        ser = InterviewQuestionUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        answer = ser.validated_data["answer"]

        turn.answer = answer
        turn.answered_at = timezone.now() if answer.strip() else None
        turn.save(update_fields=["answer", "answered_at"])

        return Response(InterviewTurnSerializer(turn).data, status=status.HTTP_200_OK)

    def delete(self, request, session_id, order):
        session = get_object_or_404(InterviewSession, id=session_id)
        can_access_session(session, request)
        turn = get_object_or_404(InterviewTurn, session=session, order=order)
        turn.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InterviewEvaluateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, session_id):
        eval_ser = InterviewEvaluateSerializer(data=request.data)
        eval_ser.is_valid(raise_exception=True)

        session = get_object_or_404(
            InterviewSession.objects.prefetch_related("turns"), id=session_id
        )
        can_access_session(session, request)

        turns = list(session.turns.all())
        missing_orders = [turn.order for turn in turns if not turn.answer.strip()]
        if missing_orders:
            missing_display = ", ".join(str(order) for order in missing_orders)
            return Response(
                {"detail": f"Missing answers for questions: {missing_display}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        items = [
            {"order": turn.order, "question": turn.question, "answer": turn.answer}
            for turn in turns
        ]

        payload = {
            "fastapi_session_id": session.fastapi_session_id or "",
            "mode": session.mode,
            "items": items,
            "context": eval_ser.validated_data.get("context", {}),
            "include_summary": eval_ser.validated_data.get("include_summary", True),
        }

        try:
            fastapi_resp = evaluate_interview(payload)
        except InterviewEngineError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)

        results = {item.get("order"): item for item in fastapi_resp.get("results", [])}
        expected_orders = {turn.order for turn in turns}
        returned_orders = {int(order) for order in results.keys() if order is not None}
        missing_orders = expected_orders - returned_orders
        if missing_orders:
            missing_display = ", ".join(str(order) for order in sorted(missing_orders))
            return Response(
                {
                    "detail": (
                        "Interview engine returned incomplete results for orders: "
                        f"{missing_display}"
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        with transaction.atomic():
            for turn in turns:
                result = results.get(turn.order)
                if not result:
                    continue
                turn.feedback = result.get("feedback", "") or ""
                turn.score = result.get("score", None)
                turn.meta = result.get("meta", {}) or {}
                turn.save(update_fields=["feedback", "score", "meta"])

            overall = fastapi_resp.get("overall")
            if overall is not None:
                session.overall_feedback = overall.get("feedback", "") or ""
                session.overall_score = overall.get("score", None)
                session.overall_meta = overall.get("meta", {}) or {}

            session.status = InterviewSession.Status.COMPLETED
            session.ended_at = timezone.now()
            session.evaluated_at = timezone.now()
            session.save(
                update_fields=[
                    "overall_feedback",
                    "overall_score",
                    "overall_meta",
                    "status",
                    "ended_at",
                    "evaluated_at",
                    "updated_at",
                ]
            )

        session = InterviewSession.objects.prefetch_related("turns").get(id=session_id)
        return Response(InterviewSessionDetailSerializer(session).data, status=status.HTTP_200_OK)
