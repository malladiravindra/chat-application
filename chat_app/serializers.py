from rest_framework import serializers

from .models import SMSMessage
from twilio_service.services import (
    InvalidMessageError,
    InvalidPhoneNumberError,
    normalize_phone_number,
    validate_message_body,
)


class SendSMSRequestSerializer(serializers.Serializer):
    """Validates an inbound POST /api/sms/send/ request body."""
    to = serializers.CharField()
    message = serializers.CharField()

    def validate_to(self, value):
        try:
            return normalize_phone_number(value)
        except InvalidPhoneNumberError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_message(self, value):
        try:
            return validate_message_body(value)
        except InvalidMessageError as exc:
            raise serializers.ValidationError(str(exc))


class SMSMessageSerializer(serializers.ModelSerializer):
    to = serializers.CharField(source="receiver_phone_number")

    class Meta:
        model = SMSMessage
        fields = ["id", "to", "body", "status", "twilio_message_sid", "created_at"]
