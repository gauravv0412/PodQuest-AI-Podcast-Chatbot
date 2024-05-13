from django.contrib.auth.views import LoginView, LogoutView, FormView
from django.contrib.auth import login
from .forms import LoginForm, SignUpForm

# Create your views here.

class Login(LoginView):
    authentication_form = LoginForm
    template_name = 'auth/login.html'

class Logout(LogoutView):
    template_name = 'auth/logout.html'

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