from django.urls import path
from . import views

urlpatterns = [
    path('course/create/', views.create_course, name='create_course'),
    path('form/create/<int:course_id>/', views.create_form, name='create_form'),
    path('courses/', views.course_list, name='course_list'),
]