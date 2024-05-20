from .models import Podcast, Transcript, Summary
from pytube import YouTube
from django.conf import settings
import subprocess
# import requests
import os
from .rag_llm import __initialise_chain
from whisper import load_model
from celery import shared_task

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def download_audio(video_url, output_path, title):
    yt = YouTube(video_url)
    yt.title = title
    yt.streams.filter(only_audio=True).first().download(output_path=output_path)
    return output_path + '/' + title + '.mp4'

import logging
logger = logging.getLogger(__name__)


@shared_task
def download_and_transcribe_podcast(podcast_id):
    channel_layer = get_channel_layer()
    group_name = f'podcast_{podcast_id}'
    podcast = Podcast.objects.get(id=podcast_id)
    audio_path = '/podcasts/' + podcast.owner.username + '/' + podcast.title
    
    file_path = settings.MEDIA_ROOT + audio_path
    # logger.debug(f"Sending Downloading status to {group_name}")
    # async_to_sync(channel_layer.group_send)(group_name, {"type": "send_status", "message": "Downloading"})
    # time.sleep(1)
    video_file = download_audio(podcast.url, output_path=file_path, title = podcast.title)
    
    async_to_sync(channel_layer.group_send)(group_name, {"type": "send_status", "message": "Converting to Audio"})
    audio_file = video_file.replace('.mp4', '.mp3')
    subprocess.run(['ffmpeg', '-i', video_file, '-codec:a', 'libmp3lame', '-qscale:a', '2', audio_file])
    os.remove(video_file)
    
    podcast.file_path = audio_path + '/' + podcast.title + '.mp3'
    podcast.save()

    async_to_sync(channel_layer.group_send)(group_name, {"type": "send_status", "message": "Transcribing"})
    # print("Transcribing podcast: ", podcast.title)
    transcribe_and_save_podcast(podcast)
    Transcript.objects.create(podcast=podcast, file_path = audio_path + '/' + podcast.title + '.txt')
    
    podcast.processing_status = 'Completed'
    podcast.save()
    
    async_to_sync(channel_layer.group_send)(group_name, {"type": "send_status", "message": "Initialising Langchain... Redirecting"})

    # print("Generating summary for podcast: ", podcast.title)
    # summary_content = generate_summary(transcribe_content)
    # Summary.objects.create(transcript=Transcript.objects.get(podcast=podcast), summary_content=summary_content)



def transcribe_and_save_podcast(podcast):
    audio_file = os.path.join(settings.MEDIA_ROOT, podcast.file_path.name.lstrip('/'))
    print("audio_file_path:", audio_file)
    model = load_model("base", device="cuda")  # Choose the appropriate model size and device
    result = model.transcribe(audio_file)
    transcript_content = result['text']
    with open(audio_file.replace('.mp3', '.txt'), 'w') as f:
        f.write(transcript_content)
    # index_transcript_segments(podcast.id, transcript_content)
    return
    

def initialise_chain(podcast_id):
    podcast = Podcast.objects.get(id=podcast_id)
    transcript_obj = Transcript.objects.get(podcast=podcast)
    transcript_file = os.path.join(settings.MEDIA_ROOT, transcript_obj.file_path.name.lstrip('/'))
    username = podcast.owner.username
    namespace = f"{username}_{podcast_id}"
    rag_llm_chain = __initialise_chain(transcript_file, namespace)
    return rag_llm_chain


def get_llm_response(message, rag_llm_chain, session_id):
    response_text = rag_llm_chain.invoke(
        {"input": message},
        config={
            "configurable": {"session_id": session_id}
            },  # constructs a key "abc123" in `store`.
        )["answer"]
    return response_text