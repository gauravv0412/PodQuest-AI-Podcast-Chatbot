from django.shortcuts import render, redirect
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




@login_required
def submit_podcast(request):
    if request.method == 'POST':
        print(request.POST)
        title = request.POST['podcast_title']
        url = request.POST['podcast_url']
        if Podcast.objects.filter(owner=request.user, title=title).exists():
            messages.error(request, 'You already have a podcast with this name. Please choose a different name.')
            return render(request, 'index.html')
        # Create a new podcast entry
        podcast = Podcast.objects.create(owner=request.user, title=title, url=url)
        # Async task to handle download and transcription
        try:
            download_and_transcribe_podcast(podcast.id)
        except Exception as e:
            raise e
            # return render(request, 'index.html', {'error': str(e)})
        # return redirect('processing', podcast_id=podcast.id)
        return redirect('/chat_page/' + str(podcast.id))

    else:
        return render(request, 'index.html')

llm_chains = {}

@login_required
def chat_page(request, podcast_id):
    session_id = request.session.session_key
    rag_llm_chain = initialise_chain(podcast_id, session_id)
    llm_chains[session_id] = rag_llm_chain
    print(f"In chat_page initialising chain for podcast_id: {podcast_id} and session_id: {session_id}...")
    return render(request, 'chat_page.html', {'podcast_id': podcast_id})

import logging

logger = logging.getLogger(__name__)


@csrf_exempt
def process_query(request):
    session_id = request.session.session_key
    rag_llm_chain = llm_chains.get(session_id)
    print(f"In process_query for session_id: {session_id}...")
    try:
        data = json.loads(request.body)
        message = data['message']
        # Assuming Elasticsearch retrieval and GPT-3.5 generation here
        response_text = get_llm_response(message, rag_llm_chain, session_id)
        
        return JsonResponse({'reply': response_text})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)