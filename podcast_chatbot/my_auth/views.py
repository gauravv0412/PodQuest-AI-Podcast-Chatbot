from django.contrib.auth.views import LoginView, LogoutView, FormView
from django.contrib.auth import login
from .forms import LoginForm, SignUpForm
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator

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