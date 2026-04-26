from django.urls import path
from .views import *

urlpatterns = [
    path('login/', institute_login, name='institute_login'),
    path('logout/', user_logout, name='institute_logout'),
    path('dashboard/', institute_dashboard),
    path('register/', institute_register), 
    path('application/<int:app_id>/edit/', edit_application),
    path('application/<int:app_id>/view/', view_application, name='view_application'),

    # ✅ NEW: Rank List
    path('rank-list/', rank_list_view, name='rank_list'),
    path('rank-list/export/', export_rank_excel, name='export_rank_excel'),

    # ✅ ADMISSION / STUDENT REGISTRATION
    path('admission/', admission_list, name='admission_list'),
    path('admission/register/<int:app_id>/', register_student, name='register_student'),
    path('admission/register-manual/', register_manual, name='register_manual'),
    path('admission/load-subcategories/', load_subcategories, name='load_subcategories'),
    path('admission/load-classes/', load_classes, name='load_classes'),
    path('load-form-fields/', load_form_fields, name='load_form_fields'),
    path('load-exam-subjects/', load_exam_subjects, name='load_exam_subjects'),

    # ✅ NEW: Student List
    path('student-list/', student_list_view, name='student_list'),
    path('student-list/export/', export_students_excel, name='export_students_excel'),

    path('application/<int:app_id>/download/', download_application_zip, name='download_application'),
    
    # STUDENT STATUS
    path('admission/status/<int:admission_id>/', update_student_status, name='update_student_status'),
    
    # EXCEL
    path('excel/template/', download_excel_template, name='excel_template'),
    path('excel/export/', excel_export_students, name='excel_export_students'),
    path('excel/import/', excel_import_students, name='excel_import_students'),

    # ✅ ACADEMIC RELATIONSHIP PORTAL
    path('notices/', manage_notices, name='manage_notices'),
    path('timetables/', manage_timetables, name='manage_timetables'),
    path('academic-results/', enter_academic_results, name='enter_academic_results'),
]