from django.urls import path

from my_auth import views

urlpatterns = [
    path('login/', views.Login.as_view(), name = 'login'),
    path('logout/', views.Logout.as_view(), name = 'logout'),
    path("signup/", views.SignUp.as_view(), name="sign_up"),
]