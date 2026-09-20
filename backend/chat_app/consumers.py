import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Message

User = get_user_model()
logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Real-time WebSocket consumer for chat communication.
    Supports:
      - Live group chat & room-based chat
      - Real-time message exchange & database persistence
      - Typing status indicators
      - Online/offline presence broadcasting
      - Ping/pong heartbeat
    """

    async def connect(self):
        self.user = self.scope.get("user")

        # Reject unauthenticated connections
        if not self.user or not self.user.is_authenticated:
            logger.warning("Rejecting unauthenticated WebSocket connection attempt.")
            await self.accept()
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Authentication required. Provide a valid session or JWT token via ?token=<token>."
            }))
            await self.close(code=4001)
            return

        # Determine room name from URL route kwargs, defaulting to 'live_chat'
        self.room_name = self.scope.get("url_route", {}).get("kwargs", {}).get("room_name", "live_chat")
        self.room_group_name = f"chat_{self.room_name}"

        # Join the channel layer group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Update online status in database
        await self.update_user_status(self.user.id, True)

        # Confirm connection to connecting client
        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "Connected to WebSocket chat API",
            "user_id": self.user.id,
            "username": self.user.phone_number,
            "room": self.room_name
        }))

        # Broadcast online status to the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_status",
                "user_id": self.user.id,
                "username": self.user.phone_number,
                "is_online": True,
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, "user") and self.user and self.user.is_authenticated:
            # Update user offline status in database
            await self.update_user_status(self.user.id, False)

            # Broadcast offline status to the room
            if hasattr(self, "room_group_name"):
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "user_status",
                        "user_id": self.user.id,
                        "username": self.user.phone_number,
                        "is_online": False,
                    }
                )

        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        """
        Handle incoming messages from WebSocket clients.
        """
        try:
            data = json.loads(text_data)
        except Exception:
            logger.error("Failed to parse incoming WebSocket JSON payload.")
            return

        msg_type = data.get("type") or data.get("action")

        # 1. Heartbeat / Ping
        if msg_type == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))
            return

        # 2. Typing status event
        if msg_type == "typing":
            is_typing = bool(data.get("is_typing", False))
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "user_typing",
                    "sender_id": self.user.id,
                    "sender_username": self.user.phone_number,
                    "is_typing": is_typing,
                }
            )
            return

        # 3. Chat message
        message_content = (data.get("message") or data.get("content") or "").strip()
        if not message_content:
            return

        receiver_id = data.get("receiver_id")
        msg_obj = await self.save_message(self.user.id, message_content, receiver_id)
        timestamp_str = msg_obj.timestamp.strftime("%H:%M")

        message_payload = {
            "type": "chat_message",
            "id": msg_obj.id,
            "message": message_content,
            "content": message_content,
            "sender_id": self.user.id,
            "sender_username": self.user.phone_number,
            "receiver_id": msg_obj.receiver_id,
            "timestamp": timestamp_str,
            "created_at": msg_obj.timestamp.isoformat(),
        }

        await self.channel_layer.group_send(self.room_group_name, message_payload)

    # ── Channel Layer Event Handlers ──

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def user_typing(self, event):
        await self.send(text_data=json.dumps(event))

    async def user_status(self, event):
        await self.send(text_data=json.dumps(event))

    # ── Database Operations ──

    @database_sync_to_async
    def update_user_status(self, user_id, is_online):
        try:
            User.objects.filter(id=user_id).update(is_online=is_online)
        except Exception as e:
            logger.error(f"Error updating user online status: {e}")

    @database_sync_to_async
    def save_message(self, sender_id, content, receiver_id=None):
        sender = User.objects.get(id=sender_id)
        receiver = None
        if receiver_id:
            try:
                receiver = User.objects.get(id=receiver_id)
            except User.DoesNotExist:
                receiver = None
        return Message.objects.create(sender=sender, receiver=receiver, content=content)
