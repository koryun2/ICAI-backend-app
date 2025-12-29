# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django import forms

from .models import User
from .models import InterviewSession, InterviewQuestion


class UserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = (
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "level",
            "tech_stack",
        )

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match.")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = UserCreationForm
    form = UserChangeForm
    model = User

    ordering = ("email",)
    list_display = (
        "email",
        "first_name",
        "last_name",
        "role",
        "level",
        "is_staff",
        "is_active",
    )
    search_fields = ("email", "first_name", "last_name", "username")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {
            "fields": (
                "first_name",
                "last_name",
                "username",
                "role",
                "level",
                "tech_stack",
            )
        }),
        ("Permissions", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email",
                "username",
                "first_name",
                "last_name",
                "role",
                "level",
                "tech_stack",
                "password1",
                "password2",
                "is_staff",
                "is_superuser",
                "is_active",
            ),
        }),
    )

class InterviewQuestionInline(admin.TabularInline):
    model = InterviewQuestion
    extra = 0
    ordering = ("order",)

@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "position", "level", "status", "created_at")
    list_filter = ("status", "level")
    search_fields = ("id", "user__email", "role", "position")
    inlines = [InterviewQuestionInline]