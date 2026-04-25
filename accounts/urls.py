from django.urls import path
from .views import student_signup, student_login, user_logout, forgot_password, reset_password_confirm

urlpatterns = [
    path('register/', student_signup, name='student_signup'),
    path('login/', student_login, name='student_login'),
    path('logout/', user_logout, name='logout'),
    path('forgot-password/', forgot_password, name='forgot_password'),
    path('reset/<uidb64>/<token>/', reset_password_confirm, name='password_reset_confirm'),
]