from django.contrib import admin

# Register your models here.

from .models import Podcast, Transcript, Summary

admin.site.register(Podcast)
admin.site.register(Transcript)
admin.site.register(Summary)
