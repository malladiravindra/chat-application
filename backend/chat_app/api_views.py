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

import datetime
import logging
import os
import secrets
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPVerification, PasswordResetOTP, SMSMessage, Conversation, ChatMessage
from .serializers import (
    SendSMSRequestSerializer,
    SMSMessageSerializer,
    SendChatSMSRequestSerializer,
    ChatMessageSerializer,
    ConversationSerializer,
)
from twilio_service.services import SMSSendError, send_sms, normalize_phone_number, InvalidPhoneNumberError

User = get_user_model()
logger = logging.getLogger(__name__)


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
    Verifies OTP:
    - If purpose="register", verifies registration OTP and activates user account.
    - If purpose="reset" or default (with phone_number + otp), verifies password reset OTP
      and returns a short-lived reset token for setting the new password.

    Request body:
        phone_number : string
        otp          : string
        purpose      : "register" | "reset"  (default: "reset" if PasswordResetOTP exists or requested)
    """

    def post(self, request):
        raw_phone = request.data.get("phone_number", "").strip()
        otp_code  = request.data.get("otp", "").strip()
        purpose   = request.data.get("purpose", "")

        if not raw_phone or not otp_code:
            return Response(
                {"error": "phone_number and otp are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            phone_number = normalize_phone_number(raw_phone)
        except InvalidPhoneNumberError:
            return Response(
                {"error": "Please enter a valid phone number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Registration Flow ────────────────────────
        if purpose == "register":
            try:
                record = OTPVerification.objects.get(
                    phone_number=phone_number, purpose="register"
                )
            except OTPVerification.DoesNotExist:
                return Response(
                    {"error": "No OTP was requested for this phone number. Please request an OTP first."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if record.is_expired():
                record.delete()
                return Response(
                    {"error": "OTP has expired. Please request a new one."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if record.max_attempts_reached():
                record.delete()
                return Response(
                    {"error": "Maximum verification attempts exceeded. Please request a new OTP."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            record.attempts += 1
            record.save()

            approved, msg = _twilio_verify_otp(phone_number, otp_code)
            if not approved:
                remaining = 3 - record.attempts
                return Response(
                    {"error": f"Invalid OTP. {remaining} attempt(s) remaining."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            record.delete()

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

        # ── Password Reset Flow (Default or purpose="reset") ────
        record = PasswordResetOTP.objects.filter(
            phone_number=phone_number, used=False
        ).order_by("-created_at").first()

        if not record:
            return Response(
                {"error": "No OTP was requested for this phone number. Please request an OTP first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if record.is_expired():
            record.used = True
            record.save(update_fields=["used"])
            return Response(
                {"error": "OTP has expired. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if record.max_attempts_reached():
            record.used = True
            record.save(update_fields=["used"])
            return Response(
                {"error": "Too many OTP attempts. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        record.attempts += 1
        record.save(update_fields=["attempts"])

        if not record.check_otp(otp_code):
            remaining = max(0, record.max_attempts - record.attempts)
            if record.max_attempts_reached():
                record.used = True
                record.save(update_fields=["used"])
                return Response(
                    {"error": "Too many OTP attempts. Please request a new OTP."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"error": f"Invalid OTP. {remaining} attempt(s) remaining."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark OTP as verified and generate temporary reset token
        reset_token = secrets.token_urlsafe(32)
        record.is_verified = True
        record.verified_at = timezone.now()
        record.reset_token = reset_token
        record.reset_token_expires_at = timezone.now() + datetime.timedelta(minutes=15)
        record.save(update_fields=["is_verified", "verified_at", "reset_token", "reset_token_expires_at"])

        return Response(
            {
                "message": "OTP verified successfully.",
                "reset_token": reset_token,
            },
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
    Validates phone number, generates 6-digit OTP, securely hashes and stores it,
    and sends it via Twilio SMS.

    Privacy-preserving: returns the same success message regardless of whether
    the phone number is registered.

    Request body:
        phone_number : string (e.g. +919876543210)
    """

    def post(self, request):
        raw_phone = request.data.get("phone_number", "").strip()

        if not raw_phone:
            return Response(
                {"error": "Please enter a valid phone number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            phone_number = normalize_phone_number(raw_phone)
        except InvalidPhoneNumberError:
            return Response(
                {"error": "Please enter a valid phone number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Rate limit / cooldown check (60 seconds) ──────
        recent_otp = PasswordResetOTP.objects.filter(
            phone_number=phone_number
        ).order_by("-created_at").first()

        if recent_otp:
            elapsed = (timezone.now() - recent_otp.created_at).total_seconds()
            if elapsed < 60:
                return Response(
                    {"error": "Please wait before requesting another OTP."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        # ── Check whether account exists ─────────────────
        user = User.objects.filter(phone_number=phone_number, is_active=True).first()

        if user:
            # Invalidate any existing unused OTPs for this phone number
            PasswordResetOTP.objects.filter(
                phone_number=phone_number, used=False
            ).update(used=True)

            # Generate secure random 6-digit numeric OTP
            otp_code = f"{secrets.randbelow(900000) + 100000}"

            # Create PasswordResetOTP record
            reset_record = PasswordResetOTP(
                user=user,
                phone_number=phone_number,
                expires_at=timezone.now() + datetime.timedelta(minutes=5),
                max_attempts=5,
            )
            reset_record.set_otp(otp_code)
            reset_record.save()

            sms_body = (
                f"Your password reset OTP is {otp_code}. "
                f"This OTP is valid for 5 minutes. Do not share this OTP with anyone."
            )
            try:
                send_sms(phone_number, sms_body)
                if settings.DEBUG:
                    logger.info("Sent password reset OTP SMS to %s", phone_number)
            except SMSSendError as exc:
                logger.error("Twilio SMS send failure for %s: %s", phone_number, exc)
                if settings.DEBUG:
                    print("\n" + "=" * 60)
                    print(f"🔑 [DEBUG DEV OTP CODE] For {phone_number}: {otp_code}")
                    print(f"   (Twilio note: {exc})")
                    print("=" * 60 + "\n")
                else:
                    return Response(
                        {"error": "Failed to send SMS. Please try again later."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            except Exception as exc:
                logger.exception("Unexpected error dispatching OTP to %s", phone_number)
                if settings.DEBUG:
                    print(f"\n🔑 [DEBUG DEV OTP CODE] For {phone_number}: {otp_code}\n")
                else:
                    return Response(
                        {"error": "Failed to send SMS. Please try again later."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

        return Response(
            {"message": "If an account exists for this phone number, an OTP has been sent."},
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────
#  6. Resend OTP — POST /api/auth/resend-otp/
# ─────────────────────────────────────────────

class ResendOTPView(APIView):
    """
    Resends a password-reset OTP with cooldown enforcement.

    Request body:
        phone_number : string
    """

    def post(self, request):
        raw_phone = request.data.get("phone_number", "").strip()

        if not raw_phone:
            return Response(
                {"error": "Please enter a valid phone number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            phone_number = normalize_phone_number(raw_phone)
        except InvalidPhoneNumberError:
            return Response(
                {"error": "Please enter a valid phone number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Rate limit / cooldown check (60 seconds) ──────
        recent_otp = PasswordResetOTP.objects.filter(
            phone_number=phone_number
        ).order_by("-created_at").first()

        if recent_otp:
            elapsed = (timezone.now() - recent_otp.created_at).total_seconds()
            if elapsed < 60:
                return Response(
                    {"error": "Please wait before requesting another OTP."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        user = User.objects.filter(phone_number=phone_number, is_active=True).first()
        if user:
            PasswordResetOTP.objects.filter(
                phone_number=phone_number, used=False
            ).update(used=True)

            otp_code = f"{secrets.randbelow(900000) + 100000}"
            reset_record = PasswordResetOTP(
                user=user,
                phone_number=phone_number,
                expires_at=timezone.now() + datetime.timedelta(minutes=5),
                max_attempts=5,
            )
            reset_record.set_otp(otp_code)
            reset_record.save()

            sms_body = (
                f"Your password reset OTP is {otp_code}. "
                f"This OTP is valid for 5 minutes. Do not share this OTP with anyone."
            )
            try:
                send_sms(phone_number, sms_body)
            except SMSSendError as exc:
                logger.error("Twilio SMS resend failure for %s: %s", phone_number, exc)
                if settings.DEBUG:
                    print("\n" + "=" * 60)
                    print(f"🔑 [DEBUG DEV RESEND OTP CODE] For {phone_number}: {otp_code}")
                    print(f"   (Twilio note: {exc})")
                    print("=" * 60 + "\n")
                else:
                    return Response(
                        {"error": "Failed to send SMS. Please try again later."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            except Exception:
                logger.exception("Unexpected error resending OTP to %s", phone_number)
                if settings.DEBUG:
                    print(f"\n🔑 [DEBUG DEV RESEND OTP CODE] For {phone_number}: {otp_code}\n")
                else:
                    return Response(
                        {"error": "Failed to send SMS. Please try again later."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

        return Response(
            {"message": "If an account exists for this phone number, an OTP has been sent."},
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────
#  7. Reset Password — POST /api/auth/reset-password/
# ─────────────────────────────────────────────

class ResetPasswordView(APIView):
    """
    Resets user password using the temporary reset token issued after OTP verification.

    Request body (standard flow):
        reset_token      : string
        new_password     : string
        confirm_password : string

    Request body (legacy direct flow with phone_number and OTP):
        phone_number     : string
        otp              : string
        new_password     : string
        confirm_password : string
    """

    def post(self, request):
        reset_token      = request.data.get("reset_token", "").strip()
        phone_number_raw = request.data.get("phone_number", "").strip()
        otp_code         = request.data.get("otp", "").strip()
        new_password     = request.data.get("new_password", "")
        confirm_password = request.data.get("confirm_password", "")

        if not new_password or not confirm_password:
            return Response(
                {"error": "new_password and confirm_password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_password:
            return Response(
                {"error": "Passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── 1. Primary flow: Token-based reset ──────────
        if reset_token:
            record = PasswordResetOTP.objects.filter(reset_token=reset_token).first()
            if not record or not record.is_verified or record.used:
                return Response(
                    {"error": "Invalid or expired reset token. Please request a new OTP."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if record.is_token_expired():
                record.used = True
                record.save(update_fields=["used"])
                return Response(
                    {"error": "Reset token has expired. Please request a new OTP."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = record.user
            if not user:
                return Response(
                    {"error": "User not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Validate password using Django's password validators
            try:
                validate_password(new_password, user=user)
            except ValidationError as exc:
                return Response(
                    {"error": " ".join(exc.messages)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.set_password(new_password)
            user.save()

            # Mark token as used and invalidate any remaining active OTPs
            record.used = True
            record.save(update_fields=["used"])
            PasswordResetOTP.objects.filter(phone_number=record.phone_number, used=False).update(used=True)

            return Response(
                {"message": "Password reset successfully."},
                status=status.HTTP_200_OK,
            )

        # ── 2. Direct flow: phone_number + otp ──────────
        if phone_number_raw and otp_code:
            try:
                phone_number = normalize_phone_number(phone_number_raw)
            except InvalidPhoneNumberError:
                return Response(
                    {"error": "Please enter a valid phone number."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            record = PasswordResetOTP.objects.filter(
                phone_number=phone_number, used=False
            ).order_by("-created_at").first()

            if not record:
                return Response(
                    {"error": "No OTP was requested for this phone number. Please request an OTP first."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if record.is_expired():
                record.used = True
                record.save(update_fields=["used"])
                return Response(
                    {"error": "OTP has expired. Please request a new OTP."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if record.max_attempts_reached():
                record.used = True
                record.save(update_fields=["used"])
                return Response(
                    {"error": "Too many OTP attempts. Please request a new OTP."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            record.attempts += 1
            record.save(update_fields=["attempts"])

            if not record.check_otp(otp_code):
                remaining = max(0, record.max_attempts - record.attempts)
                if record.max_attempts_reached():
                    record.used = True
                    record.save(update_fields=["used"])
                    return Response(
                        {"error": "Too many OTP attempts. Please request a new OTP."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                return Response(
                    {"error": f"Invalid OTP. {remaining} attempt(s) remaining."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = record.user
            if not user:
                return Response(
                    {"error": "User not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            try:
                validate_password(new_password, user=user)
            except ValidationError as exc:
                return Response(
                    {"error": " ".join(exc.messages)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.set_password(new_password)
            user.save()

            record.is_verified = True
            record.used = True
            record.verified_at = timezone.now()
            record.save(update_fields=["is_verified", "used", "verified_at"])
            PasswordResetOTP.objects.filter(phone_number=phone_number, used=False).update(used=True)

            return Response(
                {"message": "Password reset successfully."},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"error": "reset_token or (phone_number and otp) is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ─────────────────────────────────────────────
#  SMS API Views (real SMS via Twilio — separate from in-app chat)
# ─────────────────────────────────────────────

class SendSMSView(APIView):
    """
    POST /api/sms/send/ — sends a real SMS to a phone number via Twilio.

    Request body:
        to      : string  (receiver phone number, E.164 preferred)
        message : string  (<= 160 characters)

    The Twilio sender (from-number / messaging service) always comes
    from backend settings; the frontend cannot supply or override it.
    Requires authentication and is rate-limited per user (see
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['sms_send']) since every
    successful call sends a real, billable SMS.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "sms_send"

    def post(self, request):
        serializer = SendSMSRequestSerializer(data=request.data)
        if not serializer.is_valid():
            first_field, first_errors = next(iter(serializer.errors.items()))
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(first_errors[0])}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        to_number = serializer.validated_data["to"]
        body = serializer.validated_data["message"]

        sms = SMSMessage.objects.create(
            sender=request.user,
            receiver_phone_number=to_number,
            body=body,
            status=SMSMessage.STATUS_QUEUED,
        )

        try:
            result = send_sms(to_number, body)
        except SMSSendError as exc:
            sms.status = SMSMessage.STATUS_FAILED
            sms.error_message = str(exc)[:255]
            sms.error_code = str(exc.twilio_code or "")[:20]
            sms.save(update_fields=["status", "error_message", "error_code", "updated_at"])
            logger.warning("SMS send failed sms_id=%s code=%s", sms.id, sms.error_code)
            return Response(
                {"success": False, "error": {"code": "SMS_SEND_FAILED", "message": "Unable to send SMS."}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        sms.twilio_message_sid = result.sid
        if result.status in dict(SMSMessage.STATUS_CHOICES):
            sms.status = result.status
        sms.save(update_fields=["twilio_message_sid", "status", "updated_at"])

        return Response(
            {"success": True, "message": SMSMessageSerializer(sms).data},
            status=status.HTTP_201_CREATED,
        )


class SMSStatusView(APIView):
    """
    GET /api/sms/<id>/ — returns the current delivery status of an SMS
    the requesting user sent. The database (updated by the Twilio status
    webhook) is the source of truth; the frontend polls this to refresh
    the displayed status after sending.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            sms = SMSMessage.objects.get(pk=pk, sender=request.user)
        except SMSMessage.DoesNotExist:
            return Response({"error": "SMS message not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({"message": SMSMessageSerializer(sms).data})


class TwilioSMSStatusWebhookView(APIView):
    """
    POST /api/twilio/sms/status/ — Twilio delivery-status callback.

    Configure this URL (publicly reachable over HTTPS) as the
    status_callback for outbound messages. Twilio is not one of our
    users, so this endpoint is unauthenticated but verifies the
    X-Twilio-Signature header against TWILIO_AUTH_TOKEN — requests that
    fail signature validation are rejected.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if not self._is_valid_twilio_signature(request):
            logger.warning("Rejected Twilio status callback with invalid signature.")
            return Response({"error": "Invalid signature."}, status=status.HTTP_403_FORBIDDEN)

        message_sid = request.data.get("MessageSid") or request.data.get("SmsSid")
        message_status = (request.data.get("MessageStatus") or "").strip().upper()
        error_code = request.data.get("ErrorCode", "")

        if not message_sid:
            return Response({"error": "Missing MessageSid."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            sms = SMSMessage.objects.get(twilio_message_sid=message_sid)
        except SMSMessage.DoesNotExist:
            logger.info("Twilio status callback for unknown sid=%s", message_sid)
            # Twilio only cares that we returned 2xx; nothing to update locally.
            return Response({"message": "ignored"}, status=status.HTTP_200_OK)

        update_fields = ["updated_at"]
        if message_status in dict(SMSMessage.STATUS_CHOICES):
            sms.status = message_status
            update_fields.append("status")
        if error_code:
            sms.error_code = str(error_code)[:20]
            update_fields.append("error_code")

        sms.save(update_fields=update_fields)
        return Response({"message": "ok"}, status=status.HTTP_200_OK)

    @staticmethod
    def _is_valid_twilio_signature(request) -> bool:
        auth_token = settings.TWILIO_AUTH_TOKEN
        if not auth_token:
            return False

        from twilio.request_validator import RequestValidator

        validator = RequestValidator(auth_token)
        signature = request.META.get("HTTP_X_TWILIO_SIGNATURE", "")
        url = request.build_absolute_uri()
        params = request.data.dict() if hasattr(request.data, "dict") else dict(request.data)
        return validator.validate(url, params, signature)


# ─────────────────────────────────────────────
#  Chat SMS API Views  (Conversation + ChatMessage)
# ─────────────────────────────────────────────

class ChatSendSMSView(APIView):
    """
    POST /api/chat/send-sms/

    Sends a real SMS via Twilio, creates/finds a Conversation for the
    (user, phone_number) pair, and stores the ChatMessage.

    Request body:
        phone_number : string  (E.164, e.g. +919876543210)
        message      : string  (<= 160 chars)

    Response (success):
        {
          "success": true,
          "message": "SMS sent successfully",
          "message_sid": "SMxxxxxx",
          "status": "queued",
          "data": { ...ChatMessage fields... }
        }
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "sms_send"

    def post(self, request):
        # 1. Validate request data
        serializer = SendChatSMSRequestSerializer(data=request.data)
        if not serializer.is_valid():
            first_field, first_errors = next(iter(serializer.errors.items()))
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "field": first_field,
                        "message": str(first_errors[0]),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        phone_number = serializer.validated_data["phone_number"]
        message_body = serializer.validated_data["message"]

        # 2. Find or create the Conversation for this user <-> phone pair
        conversation, _ = Conversation.objects.get_or_create(
            user=request.user,
            phone_number=phone_number,
        )

        # 3. Attempt to send via Twilio
        try:
            result = send_sms(phone_number, message_body)
        except SMSSendError as exc:
            # Save a failed ChatMessage so history shows the attempt
            chat_msg = ChatMessage.objects.create(
                conversation=conversation,
                sender=request.user.phone_number,
                recipient_phone=phone_number,
                message_body=message_body,
                direction=ChatMessage.DIRECTION_OUTGOING,
                status=ChatMessage.STATUS_FAILED,
            )
            # Bump conversation updated_at
            conversation.save(update_fields=["updated_at"])

            logger.warning(
                "ChatSendSMSView: Twilio send failed user=%s to=%s err=%s",
                request.user.phone_number, phone_number, exc,
            )
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "SMS_SEND_FAILED",
                        "message": "Unable to send SMS. Please check the phone number and try again.",
                    },
                    "data": ChatMessageSerializer(chat_msg).data,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 4. Store the successful ChatMessage
        chat_msg = ChatMessage.objects.create(
            conversation=conversation,
            sender=request.user.phone_number,
            recipient_phone=phone_number,
            message_body=message_body,
            direction=ChatMessage.DIRECTION_OUTGOING,
            twilio_message_sid=result.sid,
            status=result.status.lower(),
        )

        # Bump conversation updated_at so it surfaces at the top of the list
        conversation.save(update_fields=["updated_at"])

        logger.info(
            "ChatSendSMSView: SMS sent user=%s to=%s sid=%s",
            request.user.phone_number, phone_number, result.sid,
        )

        return Response(
            {
                "success": True,
                "message": "SMS sent successfully",
                "message_sid": result.sid,
                "status": result.status.lower(),
                "data": ChatMessageSerializer(chat_msg).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ConversationListView(APIView):
    """
    GET /api/chat/conversations/

    Returns all conversations for the authenticated user, ordered
    by most recently updated first. Includes last-message preview.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = (
            Conversation.objects
            .filter(user=request.user)
            .prefetch_related("messages")
            .order_by("-updated_at")
        )
        serializer = ConversationSerializer(conversations, many=True)
        return Response(
            {"success": True, "conversations": serializer.data},
            status=status.HTTP_200_OK,
        )


class ConversationDetailView(APIView):
    """
    GET /api/chat/conversations/<pk>/messages/

    Returns the paginated message history for a specific conversation.
    Only the owner of the conversation can access it.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            conversation = Conversation.objects.get(pk=pk, user=request.user)
        except Conversation.DoesNotExist:
            return Response(
                {"error": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        messages_qs = conversation.messages.order_by("created_at")
        serializer = ChatMessageSerializer(messages_qs, many=True)
        return Response(
            {
                "success": True,
                "conversation": ConversationSerializer(conversation).data,
                "messages": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class TwilioInboundWebhookView(APIView):
    """
    POST /api/chat/inbound/

    Twilio posts here when an SMS is received on the Twilio number.
    Validates the Twilio signature and stores an 'incoming' ChatMessage.
    This endpoint is unauthenticated (called by Twilio, not a browser).
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        # Validate Twilio signature to prevent spoofing
        if not TwilioSMSStatusWebhookView._is_valid_twilio_signature(request):
            logger.warning("TwilioInboundWebhookView: rejected request with invalid signature.")
            return Response(
                {"error": "Invalid signature."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from_number = (request.data.get("From") or "").strip()
        to_number   = (request.data.get("To")   or "").strip()
        body        = (request.data.get("Body")  or "").strip()
        message_sid = (request.data.get("MessageSid") or "").strip()

        if not from_number or not body:
            return Response(
                {"error": "Missing From or Body."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Try to match to an existing conversation (any user who has
        # talked to this phone number).  If multiple, use most recent.
        from django.contrib.auth import get_user_model as _get_user_model
        UserModel = _get_user_model()

        conversation = (
            Conversation.objects
            .filter(phone_number=from_number)
            .order_by("-updated_at")
            .first()
        )

        if conversation is None:
            # No existing conversation — skip storing (or create a default)
            logger.info(
                "TwilioInboundWebhookView: no conversation for from=%s, dropping.",
                from_number,
            )
            return Response({"message": "ok"}, status=status.HTTP_200_OK)

        ChatMessage.objects.create(
            conversation=conversation,
            sender=from_number,
            recipient_phone=to_number,
            message_body=body,
            direction=ChatMessage.DIRECTION_INCOMING,
            twilio_message_sid=message_sid,
            status=ChatMessage.STATUS_RECEIVED,
        )
        conversation.save(update_fields=["updated_at"])

        logger.info(
            "TwilioInboundWebhookView: stored incoming message from=%s sid=%s",
            from_number, message_sid,
        )
        return Response({"message": "ok"}, status=status.HTTP_200_OK)
