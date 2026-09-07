import json
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from channels.testing import WebsocketCommunicator
from chat_application.asgi import application
from chat_app.models import Message

User = get_user_model()


class WebSocketChatApiTests(TransactionTestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            phone_number="+919999999991",
            password="testpassword123",
            is_verified=True
        )
        self.user2 = User.objects.create_user(
            phone_number="+919999999992",
            password="testpassword123",
            is_verified=True
        )
        # Generate JWT tokens for testing WebSocket API authentication
        self.token1 = str(RefreshToken.for_user(self.user1).access_token)
        self.token2 = str(RefreshToken.for_user(self.user2).access_token)

    async def test_websocket_authentication_rejected_for_anonymous(self):
        """Unauthenticated clients without valid session/token should be rejected."""
        communicator = WebsocketCommunicator(application, "/ws/chat/")
        connected, _ = await communicator.connect()
        # Consumer accepts and immediately sends error then closes (code 4001)
        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], "error")
        await communicator.disconnect()

    async def test_websocket_chat_communication_and_persistence(self):
        """Two users connect over WebSocket API, exchange messages, and persist to DB."""
        # Connect User 1 with JWT token in query string
        comm1 = WebsocketCommunicator(application, f"/ws/chat/?token={self.token1}")
        connected1, _ = await comm1.connect()
        self.assertTrue(connected1)

        # First message: connection_established
        init1 = await comm1.receive_json_from()
        self.assertEqual(init1["type"], "connection_established")
        self.assertEqual(init1["username"], self.user1.phone_number)

        # Second message: user_status (online: True)
        status1 = await comm1.receive_json_from()
        self.assertEqual(status1["type"], "user_status")
        self.assertTrue(status1["is_online"])

        # Connect User 2
        comm2 = WebsocketCommunicator(application, f"/ws/chat/?token={self.token2}")
        connected2, _ = await comm2.connect()
        self.assertTrue(connected2)

        init2 = await comm2.receive_json_from()
        self.assertEqual(init2["type"], "connection_established")

        # User 2 receives their own status
        status2_self = await comm2.receive_json_from()
        self.assertEqual(status2_self["type"], "user_status")

        # User 1 receives User 2's online status broadcast
        status2_broadcast = await comm1.receive_json_from()
        self.assertEqual(status2_broadcast["type"], "user_status")
        self.assertEqual(status2_broadcast["username"], self.user2.phone_number)

        # User 1 sends typing indicator
        await comm1.send_json_to({
            "type": "typing",
            "is_typing": True
        })

        # User 2 receives typing notification
        typing_event = await comm2.receive_json_from()
        self.assertEqual(typing_event["type"], "user_typing")
        self.assertEqual(typing_event["sender_username"], self.user1.phone_number)
        self.assertTrue(typing_event["is_typing"])

        # User 1 also receives the broadcast typing event from group layer
        typing_event_self = await comm1.receive_json_from()
        self.assertEqual(typing_event_self["type"], "user_typing")

        # User 1 sends a chat message
        test_message = "Hello from WebSocket API communication!"
        await comm1.send_json_to({
            "message": test_message
        })

        # Both User 1 and User 2 receive the broadcast message
        msg1 = await comm1.receive_json_from()
        self.assertEqual(msg1["type"], "chat_message")
        self.assertEqual(msg1["message"], test_message)
        self.assertEqual(msg1["sender_username"], self.user1.phone_number)

        msg2 = await comm2.receive_json_from()
        self.assertEqual(msg2["type"], "chat_message")
        self.assertEqual(msg2["message"], test_message)
        self.assertEqual(msg2["sender_username"], self.user1.phone_number)

        # User 2 responds with ping
        await comm2.send_json_to({"type": "ping"})
        pong_event = await comm2.receive_json_from()
        self.assertEqual(pong_event["type"], "pong")

        # Disconnect both
        await comm1.disconnect()
        await comm2.disconnect()

        # Verify message persisted in database
        saved_msg = await Message.objects.filter(content=test_message).afirst()
        self.assertIsNotNone(saved_msg)
        self.assertEqual(saved_msg.content, test_message)
        self.assertEqual(saved_msg.sender_id, self.user1.id)
