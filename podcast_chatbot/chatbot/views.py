from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from rest_framework import viewsets
from .models import Podcast, Transcript, Summary
from .serializers import PodcastEpisodeSerializer, TranscriptSerializer, SummarySerializer
from django.contrib.auth.decorators import login_required
from .tasks import *
from .rag_llm import *
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
import json
from django.conf import settings
import time
import re
import requests

import logging

logger = logging.getLogger(__name__)


# Create your views here.

def index(request):
    # return HttpResponse("Podcast ChatBot... Coming Soon!!!")
    return render(request, 'index.html')

class PodcastViewSet(viewsets.ModelViewSet):
    queryset = Podcast.objects.all()
    serializer_class = PodcastEpisodeSerializer

class TranscriptViewSet(viewsets.ModelViewSet):
    queryset = Transcript.objects.all()
    serializer_class = TranscriptSerializer

class SummaryViewSet(viewsets.ModelViewSet):
    queryset = Summary.objects.all()
    serializer_class = SummarySerializer


def FAQs(request):
    # faq = {}
    json_file_path = os.path.join(settings.BASE_DIR, 'chatbot/data/faqs.json')
    with open(json_file_path) as f:
        faq = json.load(f)
    # print(faq)
    return render(request, 'FAQs.html', {"faqs": faq})

def about(request):
    return render(request, 'about.html')

def loading_page(request):
    task_id = request.GET.get('task_id')
    podcast_id = request.GET.get('podcast_id')
    podcast = get_object_or_404(Podcast, id=podcast_id)
    
    if podcast.processing_status == 'Completed':
        return redirect('chat_page', podcast_id=podcast_id)

    # return render(request, 'loading.html', {'podcast_id': podcast_id})
    return render(request, 'loading.html', {'task_id': task_id, 'podcast_id': podcast_id})

def clean_podcast_url(url):
    msg = "Success"
    pattern = re.compile(r'^(https?\:\/\/)?(www\.youtube\.com|youtu\.?be)\/.+$')
    if not pattern.match(url):
        msg = 'Please enter a valid YouTube URL.'

    # Extract the video ID from the URL
    video_id = extract_video_id(url)
    if not video_id:
        msg = 'Please enter a valid YouTube URL.'


    # Check if the video exists using YouTube Data API
    if not video_exists(video_id):
        msg = 'The video does not exist. Please enter a valid YouTube URL.'

    return msg

def extract_video_id(url):
    # Extract the video ID from the URL
    pattern = re.compile(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*')
    match = pattern.search(url)
    return match.group(1) if match else None

def video_exists(video_id):
    # Replace 'YOUR_API_KEY' with your actual YouTube Data API key
    api_key = settings.YT_API_KEY
    url = f'https://www.googleapis.com/youtube/v3/videos?id={video_id}&key={api_key}&part=id'
    response = requests.get(url)
    data = response.json()
    return data['pageInfo']['totalResults'] == 1

@login_required
def submit_podcast(request):
    if request.method == 'POST':
        title = request.POST['podcast_title']
        url = request.POST['podcast_url']
        if Podcast.objects.filter(owner=request.user, title=title).exists():
            messages.error(request, 'You already have a podcast with this name. Please choose a different name.')
            return render(request, 'index.html')
        msg = clean_podcast_url(url)
        if msg != "Success":
            messages.error(request, msg)
            return render(request, 'index.html')
        podcast = Podcast.objects.create(owner=request.user, title=title, url=url)

        # Initiate asynchronous task
        task_id = download_and_transcribe_podcast.delay(podcast.id).id
        return redirect('/loading/?task_id=' + str(task_id) + '&podcast_id=' + str(podcast.id))
    else:
        return render(request, 'index.html')

llm_chains = {}

@login_required
def chat_page(request, podcast_id):
    # session_id = request.session.session_key
    session_id = request.user.username + '_' + str(podcast_id) + '_session'
    # logger.error(f"In chat_page initialising chain for podcast_id: {podcast_id} and session_id: {session_id}...")
    podcast_title = Podcast.objects.get(id=podcast_id).title
    if Summary.objects.filter(transcript__podcast__id=podcast_id).exists():
        podcast_summary = Summary.objects.get(transcript__podcast__id=podcast_id).summary_content
    else:
        # Check data freshness...
        # time.sleep(3)
        check_data_freshness(request.user.username + '_' + str(podcast_id))
        summary_prompt = "Please provide a brief summary of the podcast."
        rag_llm_chain = initialise_chain(podcast_id)
        llm_chains[session_id] = rag_llm_chain
        podcast_summary = get_llm_response(summary_prompt, rag_llm_chain, session_id)
        Summary.objects.create(transcript=Transcript.objects.get(podcast=Podcast.objects.get(id=podcast_id)), summary_content=podcast_summary)
        return reset_chat(request, podcast_id)
    greet_message = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.6;">
            <p><strong>Welcome to PodQuest!</strong></p>
            <p>I'm here to assist you with any questions you have about the podcast content.</p>
            <div style="padding: 10px; border-radius: 8px; margin-top: 10px; border: 1px solid #ddd;">
                <p><strong>Here's the podcast you uploaded:</strong></p>
                <p><strong>Title:</strong> {podcast_title}</p>
                <p><strong>Summary:</strong> {podcast_summary}</p>
            </div>
            <p>Feel free to ask me anything about the podcast!</p>
        </div>
        """
    chat_history = get_chat_history(redis_key="message_store:" + session_id)
    # print(chat_history)
    return render(request, 'chat_page.html', {'podcast_id': podcast_id, 'greet_message': greet_message, 'chat_history': chat_history})

@csrf_exempt
@login_required
def process_query(request):
    data = json.loads(request.body)
    podcast_id = data['podcast_id']
    user = Podcast.objects.get(id=podcast_id).owner
    session_id = user.username + '_' + str(podcast_id) + '_session'
    rag_llm_chain = llm_chains.get(session_id, None)
    if rag_llm_chain is None:
        logger.error("Initialising chain in process_query..., key not found")
        logger.error(f'llm_chains.keys: {llm_chains.keys()}')
        logger.error(f'Our session_id: {session_id}')
        rag_llm_chain = initialise_chain(podcast_id)
        llm_chains[session_id] = rag_llm_chain
    try:
        message = data['message']
        answer = get_llm_response(message, rag_llm_chain, session_id)
        response_text = f'<div style="padding: 10px; border-radius: 8px; margin-top: 10px; border: 1px solid #ddd;">{answer}</div>'
        return JsonResponse({'reply': response_text})
    except Exception as e:
            logger.error(f'Error processing query: {e}')
            logger.error(f'llm_chains.keys: {llm_chains.keys()}')
            logger.error(f'Our session_id: {session_id}')
            return JsonResponse({'error': str(e)}, status=500)
        # return JsonResponse({'error': str(e)}, status=500)

def reset_chat(request, podcast_id):
    redis_key = f"message_store:{request.user.username}_{podcast_id}_session"
    redis_client = redis.StrictRedis.from_url(settings.REDIS_URL)
    redis_client.delete(redis_key)
    return redirect('chat_page', podcast_id=podcast_id)