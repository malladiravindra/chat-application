"""
Twilio SMS service.

Talks to the Twilio Messages API. Credentials are read from Django
settings (never from the frontend, never hardcoded). Never log
TWILIO_AUTH_TOKEN or full message bodies.
"""
import logging
from dataclasses import dataclass

import phonenumbers
from django.conf import settings
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

logger = logging.getLogger(__name__)

MAX_SMS_LENGTH = 160


class InvalidPhoneNumberError(ValueError):
    """Raised when the receiver phone number cannot be normalized to E.164."""


class InvalidMessageError(ValueError):
    """Raised when the message body fails validation."""


class SMSSendError(Exception):
    """Raised when Twilio rejects or fails to send the message."""

    def __init__(self, message, twilio_code=None):
        super().__init__(message)
        self.twilio_code = twilio_code


@dataclass
class SMSSendResult:
    sid: str
    status: str


def _mask_phone(phone_number: str) -> str:
    """Masks a phone number for safe logging, e.g. +9198****210."""
    if not phone_number or len(phone_number) <= 6:
        return "***"
    return phone_number[:5] + "****" + phone_number[-3:]


def normalize_phone_number(raw_number: str) -> str:
    """
    Validates and normalizes a receiver phone number to E.164 (+<countrycode><number>).
    Raises InvalidPhoneNumberError on anything that isn't a real, dialable number.
    """
    if not raw_number or not raw_number.strip():
        raise InvalidPhoneNumberError("Enter a valid phone number including country code.")

    candidate = raw_number.strip()
    try:
        parsed = phonenumbers.parse(candidate, None)
    except phonenumbers.NumberParseException:
        raise InvalidPhoneNumberError("Enter a valid phone number including country code.")

    if not phonenumbers.is_valid_number(parsed):
        raise InvalidPhoneNumberError("Enter a valid phone number including country code.")

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def validate_message_body(body: str) -> str:
    """Validates and trims a message body. Raises InvalidMessageError if unusable."""
    if body is None:
        raise InvalidMessageError("Message cannot be empty.")

    trimmed = body.strip()
    if not trimmed:
        raise InvalidMessageError("Message cannot be empty.")

    if len(trimmed) > MAX_SMS_LENGTH:
        raise InvalidMessageError(f"Message must be {MAX_SMS_LENGTH} characters or fewer.")

    return trimmed


def _get_client() -> Client:
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise SMSSendError("SMS service is not configured.")
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def send_sms(to_phone_number: str, message_body: str) -> SMSSendResult:
    """
    Validates input and sends a single SMS through Twilio.

    The sender is always taken from backend settings (TWILIO_MESSAGING_SERVICE_SID
    if configured, otherwise TWILIO_PHONE_NUMBER) — callers cannot override it.

    Returns SMSSendResult(sid, status) on success.
    Raises InvalidPhoneNumberError, InvalidMessageError or SMSSendError on failure.
    """
    to_number = normalize_phone_number(to_phone_number)
    body = validate_message_body(message_body)

    client = _get_client()
    send_kwargs = {"to": to_number, "body": body}

    messaging_service_sid = getattr(settings, "TWILIO_MESSAGING_SERVICE_SID", "")
    if messaging_service_sid:
        send_kwargs["messaging_service_sid"] = messaging_service_sid
    elif settings.TWILIO_PHONE_NUMBER:
        send_kwargs["from_"] = settings.TWILIO_PHONE_NUMBER
    else:
        raise SMSSendError(
            "No Twilio sender configured (set TWILIO_PHONE_NUMBER or TWILIO_MESSAGING_SERVICE_SID)."
        )

    status_callback_url = getattr(settings, "TWILIO_STATUS_CALLBACK_URL", "")
    if status_callback_url:
        send_kwargs["status_callback"] = status_callback_url

    try:
        message = client.messages.create(**send_kwargs)
    except TwilioRestException as exc:
        logger.warning(
            "Twilio SMS send failed to=%s code=%s status=%s",
            _mask_phone(to_number), exc.code, exc.status,
        )
        raise SMSSendError(exc.msg or "Twilio rejected the request.", twilio_code=exc.code) from exc
    except Exception:
        logger.exception("Unexpected error sending SMS to=%s", _mask_phone(to_number))
        raise SMSSendError("Unable to send SMS.") from exc

    logger.info("SMS accepted by Twilio sid=%s status=%s", message.sid, message.status)
    return SMSSendResult(sid=message.sid, status=(message.status or "queued").upper())
