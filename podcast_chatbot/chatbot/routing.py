# routing.py
from django.urls import re_path
from .consumers import PodcastConsumer

websocket_urlpatterns = [
    re_path(r'ws/podcast/(?P<podcast_id>[\w-]+)/$', PodcastConsumer.as_asgi()),
]
