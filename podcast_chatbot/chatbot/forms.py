from django import forms

class PodcastForm(forms.Form):
    podcast_url = forms.URLField(label='Enter the podcast URL', widget=forms.URLInput(attrs={'class': 'form-control'}))
    podcast_title = forms.CharField(label='Enter the podcast title', widget=forms.TextInput(attrs={'class': 'form-control'}))