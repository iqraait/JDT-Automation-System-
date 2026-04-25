from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from .models import User
from django.http import HttpResponse


# ✅ STUDENT SIGNUP
def student_signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')

        if User.objects.filter(username=username).exists():
            return render(request, 'student/register.html', {'error': 'Username already exists'})
        
        if User.objects.filter(mobile_number=mobile).exists():
            return render(request, 'student/register.html', {'error': 'Mobile number already registered'})

        user = User.objects.create_user(
            username=username,
            email=email,
            mobile_number=mobile,
            password=password,
            role='student'
        )

        login(request, user)
        return redirect('/dashboard/')

    return render(request, 'student/register.html')


# ✅ STUDENT LOGIN
def student_login(request):
    if request.method == 'POST':
        user = authenticate(
            username=request.POST.get('username'),
            password=request.POST.get('password')
        )

        if user:
            login(request, user)
            return redirect('/dashboard/')

    return render(request, 'student/login.html')


# ✅ LOGOUT (COMMON FOR ALL USERS )
def user_logout(request):
    logout(request)
    return redirect('/accounts/login/')


# ✅ FORGOT PASSWORD
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.db.models import Q

def forgot_password(request):
    if request.method == 'POST':
        identifier = request.POST.get('identifier') # Email or Mobile
        user = User.objects.filter(Q(email=identifier) | Q(mobile_number=identifier)).first()

        if user and user.email:
            # Generate Reset Link
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            domain = request.get_host()
            reset_url = f"http://{domain}/accounts/reset/{uid}/{token}/"

            # Send Email
            subject = "Password Reset Request - JDT Automation"
            message = render_to_string('accounts/password_reset_email.html', {
                'user': user,
                'reset_url': reset_url,
            })
            send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email], fail_silently=False)
            
            return render(request, 'student/forgot_password.html', {'success': 'Reset link sent to your registered email.'})
        else:
            return render(request, 'student/forgot_password.html', {'error': 'User not found or email not registered.'})

    return render(request, 'student/forgot_password.html')

# ✅ RESET PASSWORD (ACTION)
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_decode

def reset_password_confirm(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = get_user_model().objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            new_password = request.POST.get('password')
            user.set_password(new_password)
            user.save()
            return redirect('/accounts/login/')
        return render(request, 'accounts/reset_password_confirm.html', {'uid': uidb64, 'token': token})
    else:
        return HttpResponse('Invalid or expired reset link.')