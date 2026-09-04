import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Message

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        self.room_group_name = 'live_chat'

        # Join group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Update online status and notify everyone
        await self.update_user_status(self.user, True)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type':      'user_status',
                'user_id':   self.user.id,
                'username':  self.user.phone_number,
                'is_online': True,
            }
        )

    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            await self.update_user_status(self.user, False)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type':      'user_status',
                    'user_id':   self.user.id,
                    'username':  self.user.phone_number,
                    'is_online': False,
                }
            )
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)

        if data.get('type') == 'typing':
            is_typing = data.get('is_typing', False)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type':            'user_typing',
                    'sender_id':       self.user.id,
                    'sender_username': self.user.phone_number,
                    'is_typing':       is_typing,
                }
            )
            return

        message_content = data.get('message', '').strip()
        if not message_content:
            return

        msg_obj = await self.save_message(self.user.id, message_content)
        timestamp_str = msg_obj.timestamp.strftime('%H:%M')

        message_payload = {
            'type':            'chat_message',
            'message':         message_content,
            'sender_id':       self.user.id,
            'sender_username': self.user.phone_number,
            'timestamp':       timestamp_str,
        }

        await self.channel_layer.group_send(self.room_group_name, message_payload)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type':            'chat_message',
            'message':         event['message'],
            'sender_id':       event['sender_id'],
            'sender_username': event['sender_username'],
            'timestamp':       event['timestamp'],
        }))

    async def user_status(self, event):
        await self.send(text_data=json.dumps({
            'type':      'user_status',
            'user_id':   event['user_id'],
            'username':  event['username'],
            'is_online': event['is_online'],
        }))

    async def user_typing(self, event):
        await self.send(text_data=json.dumps({
            'type':            'user_typing',
            'sender_id':       event['sender_id'],
            'sender_username': event['sender_username'],
            'is_typing':       event['is_typing'],
        }))

    @database_sync_to_async
    def update_user_status(self, user, is_online):
        """
        Update online status directly on CustomUser
        (no separate UserProfile needed).
        """
        User.objects.filter(id=user.id).update(is_online=is_online)

    @database_sync_to_async
    def save_message(self, sender_id, content):
        sender = User.objects.get(id=sender_id)
        return Message.objects.create(sender=sender, content=content)
