from django.urls import path
from .views import student_register, student_login
from .views import user_logout

urlpatterns = [
    path('register/', student_register),
    path('login/', student_login),
    path('logout/', user_logout, name='logout'),
]