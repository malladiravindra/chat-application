"""
Mobile Number Authentication API Views
======================================
POST /api/auth/register/         — Create unverified user + send OTP
POST /api/auth/send-otp/         — (Re-)send OTP for a given purpose
POST /api/auth/verify-otp/       — Verify OTP → activate account
POST /api/auth/login/            — Phone + password → JWT tokens
POST /api/auth/forgot-password/  — Send password-reset OTP
POST /api/auth/reset-password/   — Verify OTP + set new password

Security:
  • OTP expiry     : 5 minutes (Twilio Verify native + local fallback)
  • Max attempts   : 3 per OTP (tracked in OTPVerification.attempts)
  • Rate limiting  : 1 OTP request per phone per 60 seconds
  • Passwords      : hashed via Django's default PBKDF2 hasher
"""

import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPVerification

User = get_user_model()


# ─────────────────────────────────────────────
#  Twilio Helper
# ─────────────────────────────────────────────

def _twilio_send_otp(phone_number: str) -> tuple[bool, str]:
    """
    Sends OTP via Twilio Verify API.
    Falls back to console mock if credentials are not configured.
    Returns (success: bool, message: str).
    """
    sid   = settings.TWILIO_ACCOUNT_SID
    token = settings.TWILIO_AUTH_TOKEN
    vsid  = settings.TWILIO_VERIFY_SERVICE_SID

    if sid and token and vsid:
        try:
            from twilio.rest import Client
            client = Client(sid, token)
            verification = client.verify.v2.services(vsid).verifications.create(
                to=phone_number,
                channel="sms",
            )
            return True, f"OTP sent (status: {verification.status})"
        except Exception as exc:
            return False, str(exc)
    else:
        # ── Local development mock ──
        print("=" * 50)
        print(f"[MOCK OTP]  Phone : {phone_number}")
        print(f"[MOCK OTP]  Use Twilio dashboard or set credentials in .env")
        print("=" * 50)
        return True, "OTP sent (mock — check console)"


def _twilio_verify_otp(phone_number: str, otp_code: str) -> tuple[bool, str]:
    """
    Verifies OTP against Twilio Verify API.
    Falls back to accepting '123456' as mock code when no credentials set.
    Returns (approved: bool, message: str).
    """
    sid   = settings.TWILIO_ACCOUNT_SID
    token = settings.TWILIO_AUTH_TOKEN
    vsid  = settings.TWILIO_VERIFY_SERVICE_SID

    if sid and token and vsid:
        try:
            from twilio.rest import Client
            client = Client(sid, token)
            check = client.verify.v2.services(vsid).verification_checks.create(
                to=phone_number,
                code=otp_code,
            )
            approved = check.status == "approved"
            return approved, check.status
        except Exception as exc:
            return False, str(exc)
    else:
        # ── Local development mock: accept '123456' ──
        if otp_code == "123456":
            return True, "approved (mock)"
        return False, "Invalid OTP (mock accepts '123456')"


# ─────────────────────────────────────────────
#  Rate-limit helper
# ─────────────────────────────────────────────

_RATE_LIMIT_SECONDS = 60


def _check_rate_limit(phone_number: str, purpose: str) -> bool:
    """
    Returns True if the caller is rate-limited (too soon since last request).
    """
    record = OTPVerification.objects.filter(
        phone_number=phone_number, purpose=purpose
    ).first()
    if record:
        elapsed = (timezone.now() - record.created_at).total_seconds()
        if elapsed < _RATE_LIMIT_SECONDS:
            return True
    return False


# ─────────────────────────────────────────────
#  1. Register — POST /api/auth/register/
# ─────────────────────────────────────────────

class RegisterView(APIView):
    """
    Creates an unverified user account and sends a registration OTP.

    Request body:
        phone_number    : string  (E.164 format, e.g. +919876543210)
        password        : string
        confirm_password: string
    """

    def post(self, request):
        phone_number     = request.data.get("phone_number", "").strip()
        password         = request.data.get("password", "")
        confirm_password = request.data.get("confirm_password", "")

        # ── Validation ──────────────────────────────
        if not phone_number or not password or not confirm_password:
            return Response(
                {"error": "phone_number, password, and confirm_password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if password != confirm_password:
            return Response(
                {"error": "Passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(password) < 8:
            return Response(
                {"error": "Password must be at least 8 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(phone_number=phone_number, is_verified=True).exists():
            return Response(
                {"error": "An account with this phone number already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Rate limit ──────────────────────────────
        if _check_rate_limit(phone_number, "register"):
            return Response(
                {"error": "Please wait 60 seconds before requesting another OTP."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # ── Create or update unverified user ────────
        user, _ = User.objects.get_or_create(phone_number=phone_number)
        user.set_password(password)
        user.is_verified = False
        user.is_active   = True
        user.save()

        # ── OTP tracking record ──────────────────────
        OTPVerification.objects.filter(
            phone_number=phone_number, purpose="register"
        ).delete()
        OTPVerification.objects.create(phone_number=phone_number, purpose="register")

        # ── Send OTP ─────────────────────────────────
        success, msg = _twilio_send_otp(phone_number)
        if not success:
            return Response(
                {"error": f"Failed to send OTP: {msg}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"message": "OTP sent. Please verify your phone number to activate your account."},
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────
#  2. Send OTP — POST /api/auth/send-otp/
# ─────────────────────────────────────────────

class SendOTPView(APIView):
    """
    (Re-)sends an OTP for the given purpose.

    Request body:
        phone_number : string
        purpose      : "register" | "reset"
    """

    def post(self, request):
        phone_number = request.data.get("phone_number", "").strip()
        purpose      = request.data.get("purpose", "register")

        if not phone_number:
            return Response(
                {"error": "phone_number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if purpose not in ("register", "reset"):
            return Response(
                {"error": "purpose must be 'register' or 'reset'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Rate limit ──────────────────────────────
        if _check_rate_limit(phone_number, purpose):
            return Response(
                {"error": "Please wait 60 seconds before requesting another OTP."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # ── Reset tracking record ────────────────────
        OTPVerification.objects.filter(
            phone_number=phone_number, purpose=purpose
        ).delete()
        OTPVerification.objects.create(phone_number=phone_number, purpose=purpose)

        # ── Send OTP ─────────────────────────────────
        success, msg = _twilio_send_otp(phone_number)
        if not success:
            return Response(
                {"error": f"Failed to send OTP: {msg}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"message": "OTP sent successfully."})


# ─────────────────────────────────────────────
#  3. Verify OTP — POST /api/auth/verify-otp/
# ─────────────────────────────────────────────

class VerifyOTPView(APIView):
    """
    Verifies OTP and activates the user account (purpose=register).
    For password reset, call /api/auth/reset-password/ directly.

    Request body:
        phone_number : string
        otp          : string
        purpose      : "register" | "reset"  (default: "register")
    """

    def post(self, request):
        phone_number = request.data.get("phone_number", "").strip()
        otp_code     = request.data.get("otp", "").strip()
        purpose      = request.data.get("purpose", "register")

        if not phone_number or not otp_code:
            return Response(
                {"error": "phone_number and otp are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Retrieve tracking record ─────────────────
        try:
            record = OTPVerification.objects.get(
                phone_number=phone_number, purpose=purpose
            )
        except OTPVerification.DoesNotExist:
            return Response(
                {"error": "No OTP was requested for this phone number. Please request an OTP first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Expired? ─────────────────────────────────
        if record.is_expired():
            record.delete()
            return Response(
                {"error": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Too many attempts? ────────────────────────
        if record.max_attempts_reached():
            record.delete()
            return Response(
                {"error": "Maximum verification attempts exceeded. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Verify via Twilio ─────────────────────────
        record.attempts += 1
        record.save()

        approved, msg = _twilio_verify_otp(phone_number, otp_code)
        if not approved:
            remaining = 3 - record.attempts
            return Response(
                {"error": f"Invalid OTP. {remaining} attempt(s) remaining."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Success ───────────────────────────────────
        record.delete()

        if purpose == "register":
            try:
                user = User.objects.get(phone_number=phone_number)
            except User.DoesNotExist:
                return Response(
                    {"error": "User not found. Please register first."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            user.is_verified = True
            user.save()

            # Issue JWT tokens immediately after verification
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "message": "Phone number verified. Account activated!",
                    "access":  str(refresh.access_token),
                    "refresh": str(refresh),
                },
                status=status.HTTP_200_OK,
            )

        # For 'reset' purpose, just confirm the OTP was valid
        return Response(
            {"message": "OTP verified successfully.", "verified": True},
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────
#  4. Login — POST /api/auth/login/
# ─────────────────────────────────────────────

class LoginView(APIView):
    """
    Authenticates with phone number + password and returns JWT tokens.

    Request body:
        phone_number : string
        password     : string
    """

    def post(self, request):
        phone_number = request.data.get("phone_number", "").strip()
        password     = request.data.get("password", "")

        if not phone_number or not password:
            return Response(
                {"error": "phone_number and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use our custom backend (checks is_verified internally)
        from django.contrib.auth import authenticate
        user = authenticate(request, username=phone_number, password=password)

        if user is None:
            # Give a specific message if the account exists but is unverified
            unverified = User.objects.filter(
                phone_number=phone_number, is_verified=False
            ).first()
            if unverified:
                return Response(
                    {"error": "Phone number not verified. Please complete OTP verification."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return Response(
                {"error": "Invalid phone number or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Mark online
        user.is_online = True
        user.save(update_fields=["is_online"])

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "message":     "Login successful.",
                "access":      str(refresh.access_token),
                "refresh":     str(refresh),
                "redirect_url": "/chat/",
            },
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────
#  5. Forgot Password — POST /api/auth/forgot-password/
# ─────────────────────────────────────────────

class ForgotPasswordView(APIView):
    """
    Sends a password-reset OTP to a registered phone number.

    Request body:
        phone_number : string
    """

    def post(self, request):
        phone_number = request.data.get("phone_number", "").strip()

        if not phone_number:
            return Response(
                {"error": "phone_number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure user exists and is verified
        if not User.objects.filter(phone_number=phone_number, is_verified=True).exists():
            return Response(
                {"error": "No verified account found with this phone number."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Rate limit ──────────────────────────────
        if _check_rate_limit(phone_number, "reset"):
            return Response(
                {"error": "Please wait 60 seconds before requesting another OTP."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # ── OTP tracking record ──────────────────────
        OTPVerification.objects.filter(
            phone_number=phone_number, purpose="reset"
        ).delete()
        OTPVerification.objects.create(phone_number=phone_number, purpose="reset")

        # ── Send OTP ─────────────────────────────────
        success, msg = _twilio_send_otp(phone_number)
        if not success:
            return Response(
                {"error": f"Failed to send OTP: {msg}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"message": "Password reset OTP sent to your phone."})


# ─────────────────────────────────────────────
#  6. Reset Password — POST /api/auth/reset-password/
# ─────────────────────────────────────────────

class ResetPasswordView(APIView):
    """
    Verifies OTP and resets the user's password.

    Request body:
        phone_number     : string
        otp              : string
        new_password     : string
        confirm_password : string
    """

    def post(self, request):
        phone_number     = request.data.get("phone_number", "").strip()
        otp_code         = request.data.get("otp", "").strip()
        new_password     = request.data.get("new_password", "")
        confirm_password = request.data.get("confirm_password", "")

        if not all([phone_number, otp_code, new_password, confirm_password]):
            return Response(
                {"error": "phone_number, otp, new_password, and confirm_password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_password:
            return Response(
                {"error": "Passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 8:
            return Response(
                {"error": "Password must be at least 8 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Retrieve tracking record ─────────────────
        try:
            record = OTPVerification.objects.get(
                phone_number=phone_number, purpose="reset"
            )
        except OTPVerification.DoesNotExist:
            return Response(
                {"error": "No OTP was requested. Please request a password reset OTP first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Expired? ─────────────────────────────────
        if record.is_expired():
            record.delete()
            return Response(
                {"error": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Too many attempts? ────────────────────────
        if record.max_attempts_reached():
            record.delete()
            return Response(
                {"error": "Maximum verification attempts exceeded. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Verify via Twilio ─────────────────────────
        record.attempts += 1
        record.save()

        approved, msg = _twilio_verify_otp(phone_number, otp_code)
        if not approved:
            remaining = 3 - record.attempts
            return Response(
                {"error": f"Invalid OTP. {remaining} attempt(s) remaining."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Reset password ────────────────────────────
        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user.set_password(new_password)
        user.save()

        record.delete()

        return Response(
            {"message": "Password reset successful. You can now log in with your new password."},
            status=status.HTTP_200_OK,
        )
