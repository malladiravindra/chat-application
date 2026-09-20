from rest_framework import serializers

from .models import SMSMessage, Conversation, ChatMessage
from twilio_service.services import (
    InvalidMessageError,
    InvalidPhoneNumberError,
    normalize_phone_number,
    validate_message_body,
)


# ─────────────────────────────────────────────
#  Existing SMS serializers (kept for /api/sms/send/)
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
#  Chat (Conversation + ChatMessage) serializers
# ─────────────────────────────────────────────

class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializes a single ChatMessage for API responses."""

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "conversation",
            "sender",
            "recipient_phone",
            "message_body",
            "direction",
            "twilio_message_sid",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    """Serializes a Conversation with its most-recent message preview."""

    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "phone_number",
            "created_at",
            "updated_at",
            "last_message",
            "unread_count",
        ]
        read_only_fields = fields

    def get_last_message(self, obj):
        msg = obj.messages.order_by("-created_at").first()
        if msg:
            return {
                "message_body": msg.message_body,
                "direction": msg.direction,
                "status": msg.status,
                "created_at": msg.created_at,
            }
        return None

    def get_unread_count(self, obj):
        # Count incoming messages not yet acknowledged (placeholder — extend as needed)
        return obj.messages.filter(
            direction=ChatMessage.DIRECTION_INCOMING,
            status=ChatMessage.STATUS_RECEIVED,
        ).count()


class SendChatSMSRequestSerializer(serializers.Serializer):
    """
    Validates POST /api/chat/send-sms/ request body.

    Expected fields:
        phone_number : recipient phone in E.164 (e.g. +919876543210)
        message      : SMS body (1–160 characters)
    """
    phone_number = serializers.CharField()
    message = serializers.CharField()

    def validate_phone_number(self, value):
        try:
            return normalize_phone_number(value)
        except InvalidPhoneNumberError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_message(self, value):
        try:
            return validate_message_body(value)
        except InvalidMessageError as exc:
            raise serializers.ValidationError(str(exc))
