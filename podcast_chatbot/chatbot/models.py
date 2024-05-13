from django.db import models
from my_auth.models import User
from django.conf import settings

class Podcast(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # Link to the user who uploaded the episode
    title = models.CharField(max_length=200)
    file_path = models.FileField(upload_to='podcasts/')
    upload_date = models.DateTimeField(auto_now_add=True)
    url = models.URLField()
    
    class Meta:
        unique_together = [['owner', 'title']]

    def __str__(self):
        return self.title

class Transcript(models.Model):
    podcast = models.ForeignKey(Podcast, on_delete=models.CASCADE, related_name='transcript')
    # content = models.TextField()
    file_path = models.FileField(upload_to='podcasts/')

    def __str__(self):
        return self.podcast.title

class Summary(models.Model):
    transcript = models.ForeignKey(Transcript, on_delete=models.CASCADE, related_name='summary')
    summary_content = models.TextField()

    def __str__(self):
        return self.transcript.podcast.title

# class Query(models.Model):
#     podcast = models.ForeignKey(Podcast, on_delete=models.CASCADE)
#     text = models.TextField()
#     response = models.TextField(blank=True, null=True)