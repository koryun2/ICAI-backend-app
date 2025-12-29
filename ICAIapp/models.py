# models.py
from __future__ import annotations
from typing import Any
from uuid import uuid4
from django.conf import settings
from django.utils import timezone

from django.contrib.auth.models import AbstractUser, UserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomUserManager(UserManager):
    use_in_migrations = True

    @staticmethod
    def _normalize_email_strict(email: str) -> str:
        # BaseUserManager.normalize_email lowercases the domain part; we also lower the local part
        # to avoid case-variant duplicates in practice.
        return email.strip().lower()

    def _create_user(self, email: str, password: str | None, **extra_fields: Any):
        if not email:
            raise ValueError("The email field must be set.")

        email = self._normalize_email_strict(self.normalize_email(email))

        user = self.model(email=email, **extra_fields)
        user.set_password(password)

        # Ensure optional username doesn't get stored as "" (which would break uniqueness).
        user.username = (user.username or "").strip() or None

        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email=email, password=password, **extra_fields)

    def create_superuser(self, email: str, password: str, **extra_fields: Any):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email=email, password=password, **extra_fields)


class User(AbstractUser):
    class Level(models.TextChoices):
        JUNIOR_I = "JUNIOR_I", _("Junior I")
        JUNIOR_II = "JUNIOR_II", _("Junior II")
        MID_I = "MID_I", _("Mid I")
        MID_II = "MID_II", _("Mid II")
        SENIOR = "SENIOR", _("Senior")

    username_validator = UnicodeUsernameValidator()

    # Optional username; unique only when provided (store NULL when empty).
    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        help_text=_(
            "Optional. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        ),
        validators=[username_validator],
        error_messages={"unique": _("A user with that username already exists.")},
    )

    # Required + unique; used as the login identifier.
    email = models.EmailField(_("email address"), unique=True)

    role = models.CharField(_("role"), max_length=255, blank=True)
    level = models.CharField(_("level"), max_length=16, choices=Level.choices, blank=True)

    # Flexible list of technologies, e.g. ["Python", "Django", "PostgreSQL"]
    tech_stack = models.JSONField(_("tech stack"), default=list, blank=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    def clean(self):
        super().clean()

        if self.email:
            self.email = self.email.strip().lower()

        if self.username is not None:
            self.username = self.username.strip() or None

        if self.tech_stack is None:
            self.tech_stack = []
        if not isinstance(self.tech_stack, list):
            raise ValidationError({"tech_stack": _("tech_stack must be a JSON list.")})

    def save(self, *args: Any, **kwargs: Any):
        if self.email:
            self.email = self.email.strip().lower()
        if self.username is not None:
            self.username = self.username.strip() or None
        if self.tech_stack is None:
            self.tech_stack = []
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email

class InterviewSession(models.Model):
    class Status(models.TextChoices):
        CREATED = "CREATED", _("Created")
        IN_PROGRESS = "IN_PROGRESS", _("In progress")
        COMPLETED = "COMPLETED", _("Completed")
        FAILED = "FAILED", _("Failed")
        CANCELLED = "CANCELLED", _("Cancelled")

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interview_sessions",
        verbose_name=_("user"),
    )

    role = models.CharField(_("role"), max_length=255)
    position = models.CharField(_("position"), max_length=255)
    level = models.CharField(_("level"), max_length=16, choices=User.Level.choices)

    tech_stack = models.JSONField(_("tech stack"), default=list, blank=True)

    # If FastAPI has its own id/thread id, store it here (optional but useful)
    fastapi_session_id = models.CharField(
        _("fastapi session id"),
        max_length=128,
        blank=True,
        db_index=True,
    )

    status = models.CharField(
        _("status"),
        max_length=16,
        choices=Status.choices,
        default=Status.CREATED,
    )

    overall_feedback = models.TextField(_("overall feedback"), blank=True)
    overall_score = models.IntegerField(_("overall score"), null=True, blank=True)
    overall_meta = models.JSONField(_("overall meta"), default=dict, blank=True)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    ended_at = models.DateTimeField(_("ended at"), null=True, blank=True)

    def clean(self):
        super().clean()

        self.role = (self.role or "").strip()
        self.position = (self.position or "").strip()

        if self.tech_stack is None:
            self.tech_stack = []
        if not isinstance(self.tech_stack, list):
            raise ValidationError({"tech_stack": _("tech_stack must be a JSON list.")})

    def __str__(self) -> str:
        return f"{self.id} ({self.user})"


class InterviewTurn(models.Model):
    session = models.ForeignKey(
        InterviewSession,
        on_delete=models.CASCADE,
        related_name="turns",
        verbose_name=_("session"),
    )

    order = models.PositiveIntegerField(_("order"))

    question = models.TextField(_("question"))
    answer = models.TextField(_("answer"), blank=True)
    feedback = models.TextField(_("feedback"), blank=True)

    score = models.IntegerField(_("score"), null=True, blank=True)
    meta = models.JSONField(_("meta"), default=dict, blank=True)

    asked_at = models.DateTimeField(_("asked at"), auto_now_add=True)
    answered_at = models.DateTimeField(_("answered at"), null=True, blank=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["session", "order"], name="uniq_session_turn_order")
        ]
        indexes = [
            models.Index(fields=["session", "order"]),
        ]

    def __str__(self) -> str:
        return f"{self.session_id} #{self.order}"