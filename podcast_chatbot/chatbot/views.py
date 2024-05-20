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
    print(faq)
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



@login_required
def submit_podcast(request):
    if request.method == 'POST':
        title = request.POST['podcast_title']
        url = request.POST['podcast_url']
        if Podcast.objects.filter(owner=request.user, title=title).exists():
            messages.error(request, 'You already have a podcast with this name. Please choose a different name.')
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
    rag_llm_chain = initialise_chain(podcast_id)
    llm_chains[session_id] = rag_llm_chain
    logger.error(f"In chat_page initialising chain for podcast_id: {podcast_id} and session_id: {session_id}...")
    return render(request, 'chat_page.html', {'podcast_id': podcast_id})

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
        response_text = get_llm_response(message, rag_llm_chain, session_id)
        
        return JsonResponse({'reply': response_text})
    except Exception as e:
            logger.error(f'Error processing query: {e}')
            logger.error(f'llm_chains.keys: {llm_chains.keys()}')
            logger.error(f'Our session_id: {session_id}')
            return JsonResponse({'error': str(e)}, status=500)
        # return JsonResponse({'error': str(e)}, status=500)