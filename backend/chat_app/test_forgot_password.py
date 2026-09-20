import datetime
from unittest.mock import patch

from django.contrib.auth import authenticate, get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import PasswordResetOTP
from twilio_service.services import SMSSendError, SMSSendResult

User = get_user_model()


class ForgotPasswordAndResetPasswordTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.phone = "+919876543210"
        self.user = User.objects.create_user(
            phone_number=self.phone,
            password="OldPassword123!",
            is_verified=True,
            is_active=True,
        )

    # 1. Registered phone number & OTP generation & Twilio SMS sending
    @patch("chat_app.api_views.send_sms")
    def test_forgot_password_success(self, mock_send_sms):
        mock_send_sms.return_value = SMSSendResult(sid="SMmock123", status="QUEUED")
        response = self.client.post(
            "/api/auth/forgot-password/",
            {"phone_number": self.phone},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["message"],
            "If an account exists for this phone number, an OTP has been sent.",
        )
        # Verify OTP is stored in database
        otp_record = PasswordResetOTP.objects.filter(phone_number=self.phone).first()
        self.assertIsNotNone(otp_record)
        self.assertEqual(otp_record.user, self.user)
        self.assertFalse(otp_record.is_verified)
        self.assertFalse(otp_record.used)

        # Verify SMS was dispatched
        mock_send_sms.assert_called_once()
        call_phone, call_body = mock_send_sms.call_args[0]
        self.assertEqual(call_phone, self.phone)
        self.assertIn("Your password reset OTP is", call_body)
        self.assertIn("valid for 5 minutes", call_body)

        # Ensure OTP itself is NOT returned in API response
        self.assertNotIn("otp", response.data)

    # 2. Privacy / Unregistered phone number (does not leak existence, no SMS sent)
    @patch("chat_app.api_views.send_sms")
    def test_forgot_password_unregistered_phone(self, mock_send_sms):
        response = self.client.post(
            "/api/auth/forgot-password/",
            {"phone_number": "+919999999999"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["message"],
            "If an account exists for this phone number, an OTP has been sent.",
        )
        mock_send_sms.assert_not_called()
        self.assertFalse(PasswordResetOTP.objects.filter(phone_number="+919999999999").exists())

    # 3. Invalid phone number format
    def test_forgot_password_invalid_phone(self):
        response = self.client.post(
            "/api/auth/forgot-password/",
            {"phone_number": "invalid-phone"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)

    # 4. Resend cooldown (60 seconds)
    @patch("chat_app.api_views.send_sms")
    def test_resend_cooldown_enforced(self, mock_send_sms):
        mock_send_sms.return_value = SMSSendResult(sid="SMmock123", status="QUEUED")
        # First request
        r1 = self.client.post(
            "/api/auth/forgot-password/",
            {"phone_number": self.phone},
            format="json",
        )
        self.assertEqual(r1.status_code, 200)

        # Immediate second request should trigger 429
        r2 = self.client.post(
            "/api/auth/forgot-password/",
            {"phone_number": self.phone},
            format="json",
        )
        self.assertEqual(r2.status_code, 429)
        self.assertEqual(r2.data["error"], "Please wait before requesting another OTP.")

        # Resend-otp endpoint should also enforce cooldown
        r3 = self.client.post(
            "/api/auth/resend-otp/",
            {"phone_number": self.phone},
            format="json",
        )
        self.assertEqual(r3.status_code, 429)

    # 5. Resend OTP after cooldown creates new OTP and invalidates previous
    @patch("chat_app.api_views.send_sms")
    def test_resend_otp_after_cooldown(self, mock_send_sms):
        mock_send_sms.return_value = SMSSendResult(sid="SMmock123", status="QUEUED")
        # Create initial record 65 seconds ago
        initial = PasswordResetOTP(
            user=self.user,
            phone_number=self.phone,
            expires_at=timezone.now() + datetime.timedelta(minutes=5),
            max_attempts=5,
        )
        initial.set_otp("111111")
        initial.save()
        PasswordResetOTP.objects.filter(id=initial.id).update(
            created_at=timezone.now() - datetime.timedelta(seconds=65)
        )

        response = self.client.post(
            "/api/auth/resend-otp/",
            {"phone_number": self.phone},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        initial.refresh_from_db()
        self.assertTrue(initial.used)  # Old OTP invalidated

        new_record = PasswordResetOTP.objects.filter(phone_number=self.phone, used=False).first()
        self.assertIsNotNone(new_record)
        self.assertNotEqual(new_record.id, initial.id)

    # 6. OTP verification success (returns reset token)
    def test_verify_otp_success(self):
        record = PasswordResetOTP(
            user=self.user,
            phone_number=self.phone,
            expires_at=timezone.now() + datetime.timedelta(minutes=5),
            max_attempts=5,
        )
        record.set_otp("865437")
        record.save()

        response = self.client.post(
            "/api/auth/verify-otp/",
            {"phone_number": self.phone, "otp": "865437"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "OTP verified successfully.")
        self.assertIn("reset_token", response.data)
        self.assertNotEqual(response.data["reset_token"], "865437")

        record.refresh_from_db()
        self.assertTrue(record.is_verified)
        self.assertIsNotNone(record.verified_at)
        self.assertEqual(record.reset_token, response.data["reset_token"])

    # 7. Wrong OTP (increments attempt count)
    def test_verify_otp_wrong_code(self):
        record = PasswordResetOTP(
            user=self.user,
            phone_number=self.phone,
            expires_at=timezone.now() + datetime.timedelta(minutes=5),
            max_attempts=5,
        )
        record.set_otp("865437")
        record.save()

        response = self.client.post(
            "/api/auth/verify-otp/",
            {"phone_number": self.phone, "otp": "000000"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid OTP", response.data["error"])

        record.refresh_from_db()
        self.assertEqual(record.attempts, 1)
        self.assertFalse(record.is_verified)

    # 8. Expired OTP rejected
    def test_verify_otp_expired(self):
        record = PasswordResetOTP(
            user=self.user,
            phone_number=self.phone,
            expires_at=timezone.now() - datetime.timedelta(seconds=10),
            max_attempts=5,
        )
        record.set_otp("865437")
        record.save()

        response = self.client.post(
            "/api/auth/verify-otp/",
            {"phone_number": self.phone, "otp": "865437"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "OTP has expired. Please request a new OTP.")

    # 9. Multiple wrong attempts locks OTP out
    def test_verify_otp_max_attempts(self):
        record = PasswordResetOTP(
            user=self.user,
            phone_number=self.phone,
            expires_at=timezone.now() + datetime.timedelta(minutes=5),
            max_attempts=5,
            attempts=4,
        )
        record.set_otp("865437")
        record.save()

        # 5th failed attempt
        response = self.client.post(
            "/api/auth/verify-otp/",
            {"phone_number": self.phone, "otp": "111111"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["error"],
            "Too many OTP attempts. Please request a new OTP.",
        )
        record.refresh_from_db()
        self.assertTrue(record.used)

    # 10. Reset Password success flow (reset token, password validation, hashing)
    def test_reset_password_success(self):
        record = PasswordResetOTP(
            user=self.user,
            phone_number=self.phone,
            expires_at=timezone.now() + datetime.timedelta(minutes=5),
            is_verified=True,
            reset_token="test-secret-token-xyz-12345",
            reset_token_expires_at=timezone.now() + datetime.timedelta(minutes=15),
        )
        record.set_otp("865437")
        record.save()

        new_pass = "BrandNewSecretPassword#2026"
        response = self.client.post(
            "/api/auth/reset-password/",
            {
                "reset_token": "test-secret-token-xyz-12345",
                "new_password": new_pass,
                "confirm_password": new_pass,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Password reset successfully.")

        # Check password hashed and works with authenticate
        self.user.refresh_from_db()
        auth_user_old = authenticate(username=self.phone, password="OldPassword123!")
        self.assertIsNone(auth_user_old)  # Old password no longer works

        auth_user_new = authenticate(username=self.phone, password=new_pass)
        self.assertIsNotNone(auth_user_new)  # New password works!

        # Check token marked as used
        record.refresh_from_db()
        self.assertTrue(record.used)

    # 11. Reset token cannot be reused
    def test_reset_token_cannot_be_reused(self):
        record = PasswordResetOTP(
            user=self.user,
            phone_number=self.phone,
            expires_at=timezone.now() + datetime.timedelta(minutes=5),
            is_verified=True,
            reset_token="single-use-token",
            reset_token_expires_at=timezone.now() + datetime.timedelta(minutes=15),
            used=True,
        )
        record.set_otp("865437")
        record.save()

        response = self.client.post(
            "/api/auth/reset-password/",
            {
                "reset_token": "single-use-token",
                "new_password": "AnotherNewPassword#123",
                "confirm_password": "AnotherNewPassword#123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid or expired reset token", response.data["error"])

    # 12. Reset password mismatch error
    def test_reset_password_mismatch(self):
        response = self.client.post(
            "/api/auth/reset-password/",
            {
                "reset_token": "any-token",
                "new_password": "Password1234!",
                "confirm_password": "DifferentPassword1234!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Passwords do not match.")

    # 13. Weak password rejected by Django validators
    def test_reset_password_weak_rejected(self):
        record = PasswordResetOTP(
            user=self.user,
            phone_number=self.phone,
            expires_at=timezone.now() + datetime.timedelta(minutes=5),
            is_verified=True,
            reset_token="valid-token-for-weak-pass",
            reset_token_expires_at=timezone.now() + datetime.timedelta(minutes=15),
        )
        record.set_otp("865437")
        record.save()

        response = self.client.post(
            "/api/auth/reset-password/",
            {
                "reset_token": "valid-token-for-weak-pass",
                "new_password": "short",  # < 8 chars
                "confirm_password": "short",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("too short", response.data["error"].lower())

    # 14. Twilio failure safely handled
    @patch("chat_app.api_views.send_sms")
    def test_twilio_failure_handled_safely(self, mock_send_sms):
        mock_send_sms.side_effect = SMSSendError("Twilio connection failed", twilio_code=20003)
        response = self.client.post(
            "/api/auth/forgot-password/",
            {"phone_number": self.phone},
            format="json",
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["error"], "Failed to send SMS. Please try again later.")
        # Twilio internal details not exposed
        self.assertNotIn("20003", response.data["error"])
        self.assertNotIn("connection failed", response.data["error"])
