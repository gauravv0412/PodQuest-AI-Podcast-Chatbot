from rest_framework import serializers
from .models import Podcast, Transcript, Summary

class PodcastEpisodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Podcast
        fields = ['id', 'user', 'title', 'file_path', 'upload_date']

class TranscriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transcript
        fields = ['id', 'podcast', 'content']

class SummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Summary
        fields = ['id', 'transcript', 'summary']
