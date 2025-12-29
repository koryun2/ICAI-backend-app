from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import InterviewSession, InterviewTurn

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "level",
            "tech_stack",
        )


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    tech_stack = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "password",
            "username",
            "first_name",
            "last_name",
            "role",
            "level",
            "tech_stack",
        )
        extra_kwargs = {
            "username": {"required": False, "allow_blank": True, "allow_null": True},
            "first_name": {"required": False, "allow_blank": True},
            "last_name": {"required": False, "allow_blank": True},
            "role": {"required": False, "allow_blank": True},
            "level": {"required": False, "allow_blank": True},
        }

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class MeUpdateSerializer(serializers.ModelSerializer):
    tech_stack = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "role",
            "level",
            "tech_stack",
        )
        extra_kwargs = {
            "username": {"required": False, "allow_blank": True, "allow_null": True},
        }

class InterviewTurnSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewTurn
        fields = (
            "id",
            "order",
            "question",
            "answer",
            "feedback",
            "score",
            "meta",
            "asked_at",
            "answered_at",
        )


class InterviewSessionListSerializer(serializers.ModelSerializer):
    stack = serializers.ListField(source="tech_stack", child=serializers.CharField(), required=False)

    class Meta:
        model = InterviewSession
        fields = (
            "id",
            "role",
            "position",
            "level",
            "stack",
            "status",
            "created_at",
            "updated_at",
            "started_at",
            "ended_at",
            "overall_score",
        )


class InterviewSessionDetailSerializer(serializers.ModelSerializer):
    stack = serializers.ListField(source="tech_stack", child=serializers.CharField(), required=False)
    turns = InterviewTurnSerializer(many=True, read_only=True)

    class Meta:
        model = InterviewSession
        fields = (
            "id",
            "role",
            "position",
            "level",
            "stack",
            "status",
            "fastapi_session_id",
            "overall_feedback",
            "overall_score",
            "overall_meta",
            "created_at",
            "updated_at",
            "started_at",
            "ended_at",
            "turns",
        )


class InterviewSessionCreateSerializer(serializers.ModelSerializer):
    stack = serializers.ListField(
        source="tech_stack",
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = InterviewSession
        fields = ("id", "role", "position", "level", "stack")
        read_only_fields = ("id",)


class InterviewAnswerSerializer(serializers.Serializer):
    answer = serializers.CharField(allow_blank=False)