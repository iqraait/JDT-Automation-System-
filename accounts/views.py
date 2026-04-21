from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from .models import User


# ✅ STUDENT REGISTER
def student_register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = User.objects.create_user(
            username=username,
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