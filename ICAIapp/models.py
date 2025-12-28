# models.py
from __future__ import annotations
from typing import Any

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
        MID = "MID", _("Mid")
        UPPER_MID = "UPPER_MID", _("Upper Mid")
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
