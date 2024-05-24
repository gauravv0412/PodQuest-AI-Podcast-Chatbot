# consumers.py
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
import json

logger = logging.getLogger(__name__)

class PodcastConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.podcast_id = self.scope['url_route']['kwargs']['podcast_id']
        self.room_group_name = f'podcast_{self.podcast_id}'

        logger.debug(f"Connecting to room: {self.room_group_name}")

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        logger.debug(f"Disconnecting from room: {self.room_group_name}")

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def send_status(self, event):
        message = event['message']
        logger.debug(f"Sending message to WebSocket: {message}")
        await self.send(text_data=json.dumps({
            'message': message
        }))
