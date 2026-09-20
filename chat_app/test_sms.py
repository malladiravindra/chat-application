from unittest.mock import patch

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from .models import SMSMessage
from twilio_service.services import SMSSendError, SMSSendResult

User = get_user_model()


def auth_client(user):
    client = APIClient()
    token = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


class SendSMSViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            phone_number="+919999900001", password="testpass123", is_verified=True
        )

    def test_authentication_required(self):
        client = APIClient()
        response = client.post(
            "/api/sms/send/", {"to": "+919876543210", "message": "hi"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_invalid_receiver_rejected(self):
        client = auth_client(self.user)
        response = client.post(
            "/api/sms/send/", {"to": "not-a-number", "message": "hi"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(SMSMessage.objects.count(), 0)

    def test_empty_message_rejected(self):
        client = auth_client(self.user)
        response = client.post(
            "/api/sms/send/", {"to": "+919876543210", "message": "   "}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(SMSMessage.objects.count(), 0)

    @patch("chat_app.api_views.send_sms")
    def test_valid_request_sends_via_twilio_and_saves_sid(self, mock_send_sms):
        mock_send_sms.return_value = SMSSendResult(sid="SM123456789", status="QUEUED")
        client = auth_client(self.user)

        response = client.post(
            "/api/sms/send/",
            {"to": "+919876543210", "message": "Hello, how are you?"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"]["twilio_message_sid"], "SM123456789")

        mock_send_sms.assert_called_once_with("+919876543210", "Hello, how are you?")

        sms = SMSMessage.objects.get()
        self.assertEqual(sms.sender, self.user)
        self.assertEqual(sms.receiver_phone_number, "+919876543210")
        self.assertEqual(sms.twilio_message_sid, "SM123456789")
        self.assertEqual(sms.status, "QUEUED")

    @patch("chat_app.api_views.send_sms")
    def test_twilio_failure_is_handled_safely(self, mock_send_sms):
        mock_send_sms.side_effect = SMSSendError("boom", twilio_code=21211)
        client = auth_client(self.user)

        response = client.post(
            "/api/sms/send/",
            {"to": "+919876543210", "message": "Hello"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "SMS_SEND_FAILED")
        # No Twilio internals leaked to the client
        self.assertNotIn("boom", str(response.data))

        sms = SMSMessage.objects.get()
        self.assertEqual(sms.status, "FAILED")
        self.assertEqual(sms.error_code, "21211")

    @patch("chat_app.api_views.send_sms")
    def test_rate_limiting_blocks_excess_requests(self, mock_send_sms):
        mock_send_sms.return_value = SMSSendResult(sid="SM1", status="QUEUED")
        client = auth_client(self.user)
        payload = {"to": "+919876543210", "message": "Hello"}

        with patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"sms_send": "1/min"}):
            first = client.post("/api/sms/send/", payload, format="json")
            second = client.post("/api/sms/send/", payload, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 429)


class SMSStatusWebhookTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            phone_number="+919999900002", password="testpass123", is_verified=True
        )
        self.sms = SMSMessage.objects.create(
            sender=self.user,
            receiver_phone_number="+919876543210",
            body="Hello",
            twilio_message_sid="SMabc123",
            status="QUEUED",
        )

    @patch("chat_app.api_views.TwilioSMSStatusWebhookView._is_valid_twilio_signature")
    def test_webhook_updates_matching_message(self, mock_valid_sig):
        mock_valid_sig.return_value = True
        client = APIClient()

        response = client.post(
            "/api/twilio/sms/status/",
            {"MessageSid": "SMabc123", "MessageStatus": "delivered"},
        )

        self.assertEqual(response.status_code, 200)
        self.sms.refresh_from_db()
        self.assertEqual(self.sms.status, "DELIVERED")

    @patch("chat_app.api_views.TwilioSMSStatusWebhookView._is_valid_twilio_signature")
    def test_webhook_rejects_invalid_signature(self, mock_valid_sig):
        mock_valid_sig.return_value = False
        client = APIClient()

        response = client.post(
            "/api/twilio/sms/status/",
            {"MessageSid": "SMabc123", "MessageStatus": "delivered"},
        )

        self.assertEqual(response.status_code, 403)
        self.sms.refresh_from_db()
        self.assertEqual(self.sms.status, "QUEUED")
