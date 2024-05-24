from django.contrib.auth.views import LoginView, LogoutView, FormView
from django.contrib.auth import login
from .forms import LoginForm, SignUpForm
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
import redis

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
import os
from chatbot.models import Podcast, Transcript, Summary
from django.conf import settings
import shutil
from chatbot.rag_llm import delete_namespace_pinecone
def check_user_authenticated(user):
    return not user.is_authenticated

# Create your views here.

class Login(LoginView):
    authentication_form = LoginForm
    template_name = 'auth/login.html'
    redirect_authenticated_user = True

class Logout(LogoutView):
    template_name = 'auth/logout.html'

@method_decorator(user_passes_test(check_user_authenticated, login_url='login', redirect_field_name='index'), name='dispatch')
class SignUp(FormView):
    template_name = "auth/signup.html"
    form_class = SignUpForm
    success_url = "/"
    
    def form_valid(self, form):
        user = form.save()  # Save the new user
        login(self.request, user)  # Log the user in
        return super().form_valid(form)  # Redirect to success_url

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Sign Up'  # Additional context
        return context
    
@login_required
def list_podcasts(request):
    podcasts = Podcast.objects.filter(owner=request.user)
    items = []
    message = ""
    for podcast in podcasts:
        dc = {}
        dc['title'] = podcast.title
        dc['upload_date'] = podcast.upload_date
        dc['id'] = podcast.id
        tmp = Transcript.objects.get(podcast=podcast)
        dc['summary'] = Summary.objects.get(transcript=tmp).summary_content
        items.append(dc)
    if len(items) == 0:
        message = "You have not uploaded any podcasts yet."
    return render(request, 'profile_podcasts.html', {'items': items, 'message': message})



@login_required
def delete_podcast(request, podcast_id):
    podcast = get_object_or_404(Podcast, id=podcast_id, owner=request.user)
    
    file_field = podcast.file_path
    file_path = os.path.join(settings.MEDIA_ROOT, file_field.name)
    parent_directory = settings.MEDIA_ROOT + '/' + os.path.dirname(file_path)
    shutil.rmtree(parent_directory)
    
    namespace = f"{podcast.owner.username}_{podcast_id}"
    delete_namespace_pinecone(namespace)
    
    redis_key = f"message_store:{podcast.owner.username}_{podcast_id}_session"
    redis_client = redis.StrictRedis.from_url(settings.REDIS_URL)
    redis_client.delete(redis_key)

    podcast.delete()
    
    return redirect('my_podcasts')