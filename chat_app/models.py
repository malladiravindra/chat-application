from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone


# ─────────────────────────────────────────────
#  Custom User Manager
# ─────────────────────────────────────────────

class CustomUserManager(BaseUserManager):
    """Manager that uses phone_number instead of username."""

    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("Phone number is required")
        extra_fields.setdefault("is_active", True)
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)
        extra_fields.setdefault("is_active", True)

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(phone_number, password, **extra_fields)


# ─────────────────────────────────────────────
#  Custom User Model
# ─────────────────────────────────────────────

class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    User model that uses phone_number as the primary identifier.
    Satisfies requirements: id, phone_number, password, is_verified,
    is_active, created_at, updated_at.
    """
    phone_number = models.CharField(max_length=20, unique=True)
    is_verified   = models.BooleanField(default=False)
    is_active     = models.BooleanField(default=True)
    is_staff      = models.BooleanField(default=False)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    # Chat-app extras kept for UI colour in the group chat
    is_online    = models.BooleanField(default=False)
    avatar_color = models.CharField(max_length=7, default='#6366f1')

    USERNAME_FIELD  = "phone_number"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.phone_number


# ─────────────────────────────────────────────
#  Message Model  (FK → CustomUser)
# ─────────────────────────────────────────────

class Message(models.Model):
    sender   = models.ForeignKey(
        "chat_app.CustomUser",
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    receiver = models.ForeignKey(
        "chat_app.CustomUser",
        on_delete=models.CASCADE,
        related_name="received_messages",
        null=True,
        blank=True,
    )
    content   = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read   = models.BooleanField(default=False)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        recv = self.receiver.phone_number if self.receiver else "Global"
        return f"From {self.sender.phone_number} to {recv} at {self.timestamp}"


# ─────────────────────────────────────────────
#  OTP Verification Tracking Model
# ─────────────────────────────────────────────

class OTPVerification(models.Model):
    """
    Tracks OTP request metadata for rate-limiting and attempt counting.
    The actual OTP value is managed by Twilio Verify; we only track
    when it was requested and how many check-attempts have been made.
    """
    PURPOSE_CHOICES = [
        ("register", "Register"),
        ("reset",    "Password Reset"),
    ]

    phone_number = models.CharField(max_length=20)
    purpose      = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    attempts     = models.PositiveSmallIntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        # One active OTP record per (phone, purpose) at a time
        unique_together = [("phone_number", "purpose")]

    def is_expired(self):
        """Returns True if the OTP is older than 5 minutes."""
        return (timezone.now() - self.created_at).total_seconds() > 300

    def max_attempts_reached(self):
        return self.attempts >= 3

    def __str__(self):
        return f"{self.phone_number} [{self.purpose}] — attempts: {self.attempts}"
