from django.urls import path

from . import views

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import PodcastViewSet, TranscriptViewSet, SummaryViewSet

router = DefaultRouter()
# router.register(r'', views.index, basename='index')
router.register(r'podcasts', PodcastViewSet)
router.register(r'transcripts', TranscriptViewSet)
router.register(r'summaries', SummaryViewSet)

urlpatterns = [
    path('', views.index, name='index'),
    path('submit_podcast/', views.submit_podcast, name='submit_podcast'),
    # path('chat_page/', views.chat_page, name='chat_page'),
    path('chat_page/<int:podcast_id>/', views.chat_page, name='chat_page'),
    path('process_query/', views.process_query, name='process_query'),
    path('data/', include(router.urls)),
    path('FAQs/', views.FAQs, name='FAQs'),
    path('about/', views.about, name='About'),
]