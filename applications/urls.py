from django.urls import path
from .views import *

urlpatterns = [
    path('dashboard/', dashboard, name='student_dashboard'),
    path('student-profile/', student_profile, name='student_profile'),
    path('upload-document/', upload_document, name='upload_document'),
    path('apply/', apply_course, name='apply_course'),
    path('my-applications/', my_applications, name='my_applications'),

    # ✅ AJAX
    path('load-academic-years/', load_academic_years, name='load_academic_years'),
    path('load-courses/', load_courses, name='load_courses'),
    path('load-form-fields/', load_form_fields, name='load_form_fields'),

    # ✅ NEW
    path('load-exam-subjects/', load_exam_subjects, name='load_exam_subjects'),
    path('payment/<int:app_id>/', payment_page, name='payment_page'),
    path('payment-success/<int:app_id>/', payment_success, name='payment_success'),
    path('payment/callback/ccavenue/', ccavenue_callback, name='ccavenue_callback'),
    path('payment/callback/phicommerce/', phicommerce_callback, name='phicommerce_callback'),
    path('payment/webhook/phicommerce/', phicommerce_webhook, name='phicommerce_webhook'),
    path('view/<int:app_id>/', view_application, name='view_application'),
    path('view/<int:app_id>/pdf/', download_application_pdf, name='download_application_pdf'),
]
