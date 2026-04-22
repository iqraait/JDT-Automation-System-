import os
import zipfile
from io import BytesIO
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login,logout
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from academics.models import Course, FormField, FormSection, CourseCategory, CourseSubCategory, ExamSubject, Class
from applications.models import Application, ApplicationFieldValue, FeeCategory, Admission
from .models import Institute, AcademicYear
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import HttpResponse
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
import json
import datetime
from core.utils import generate_application_pdf


User = get_user_model()


# =========================
# EMAIL CONFIGURATION (SMTP)
# =========================
# Please update your SMTP settings in settings.py or here
# You can use Gmail, Outlook, or any other SMTP provider.
# Example for Gmail:
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'your-email@gmail.com'
# EMAIL_HOST_PASSWORD = 'your-app-password'

def send_admission_email(admission):
    """Sends a selection/admission memo to the student email."""
    try:
        student = admission.application.student
        subject = f"Admission Selected - {admission.application.course.name}"
        message = f"Congratulations!\n\nYou are selected with a registered number {admission.register_number} and please login to your student portal to see the more details http://127.0.0.1:8000/accounts/login/"
        
        from_email = settings.EMAIL_HOST_USER
        recipient_list = [student.email]
        
        send_mail(subject, message, from_email, recipient_list, fail_silently=True)
    except Exception as e:
        print(f"Email failed: {e}")


# =========================
# ADMISSION LIST
# =========================
@login_required
def admission_list(request):
    institute = request.user.institute
    
    # Only "Selected" applications
    applications = Application.objects.filter(institute=institute, status='selected')
    
    # Filters
    form_id = request.GET.get('form_id')
    name = request.GET.get('name')
    category_id = request.GET.get('category_id')
    admission_year = request.GET.get('year')
    
    if form_id:
        applications = applications.filter(id=form_id)
    
    if category_id:
        applications = applications.filter(course__category_id=category_id)
        
    if admission_year:
        applications = applications.filter(academic_year_id=admission_year)
        
    processed_apps = []
    
    # Get all academic years for filter
    years = AcademicYear.objects.all()
    categories = CourseCategory.objects.all()
    
    for app in applications:
        std_name = get_student_name(app)
        
        # Name Filter
        if name and name.lower() not in std_name.lower():
            continue
            
        processed_apps.append({
            "form_no": app.id,
            "name": std_name,
            "student_first_name": app.student.first_name if app.student.first_name else std_name,
            "course": app.course,
            "academic_year": app.academic_year,
            "status": app.status,
            "is_registered": hasattr(app, 'admission'),
            "category": app.course.category.name if app.course.category else "Uncategorized",
        })

    return render(request, 'institute/admission_list.html', {
        'applications': processed_apps,
        'years': years,
        'categories': categories,
        'selected_year': admission_year,
        'selected_category_id': category_id,
        'selected_name': name,
        'selected_form_id': form_id
    })


# =========================
# REGISTER STUDENT
# =========================
@login_required
def register_student(request, app_id):
    app = get_object_or_404(Application, id=app_id)
    course = app.course
    
    if request.method == 'POST':
        # 1. Save Admission Record
        registration_id = request.POST.get('registration_id')
        student_email = request.POST.get('student_email')
        date_of_join = request.POST.get('date_of_join')
        fee_cat_id = request.POST.get('fee_category_id')
        joining_period_id = request.POST.get('joining_period_id')
        calculated_fee = request.POST.get('calculated_fee')
        
        # Update student email if changed
        if student_email and app.student.email != student_email:
            app.student.email = student_email
            app.student.save()
        discount_amount = request.POST.get('discount_amount', 0) or 0
        discount_reason = request.POST.get('discount_reason')
        final_fee = request.POST.get('final_fee')
        selected_course_id = request.POST.get('course_id')
        
        if selected_course_id:
            course = get_object_or_404(Course, id=selected_course_id)
        
        # Guardian
        care_of = request.POST.get('care_of')
        guardian_name = request.POST.get('guardian_name')
        guardian_mobile = request.POST.get('guardian_mobile')
        relationship = request.POST.get('relationship')
        guardian_address = request.POST.get('guardian_address')
        
        if Admission.objects.filter(registration_id=registration_id).exists():
            messages.error(request, "Registration ID already exists.")
            return redirect(request.path)

        # Fix: Convert date string to date object
        doj_obj = datetime.datetime.strptime(date_of_join, '%Y-%m-%d').date() if date_of_join else datetime.date.today()

        adm = Admission.objects.create(
            application=app,
            registration_id=registration_id,
            date_of_join=doj_obj,
            selected_course=course,
            fee_category_id=fee_cat_id,
            joining_period_id=joining_period_id if joining_period_id else None,
            calculated_fee=calculated_fee,
            discount_amount=discount_amount,
            discount_reason=discount_reason,
            final_fee=final_fee,
            care_of=care_of,
            guardian_name=guardian_name,
            guardian_mobile=guardian_mobile,
            relationship=relationship,
            guardian_address=guardian_address,
            assigned_class_id=request.POST.get('assigned_class_id') if request.POST.get('assigned_class_id') else None
        )

        # 2. Save Dynamic Form Fields
        fields = FormField.objects.filter(form=course.form)
        for field in fields:
            key = f"field_{field.id}"
            if field.field_type == 'file':
                file_obj = request.FILES.get(key)
                if file_obj:
                    # FIX: Handle potential duplicate values safely
                    val_obj = ApplicationFieldValue.objects.filter(application=app, field=field).first()
                    if not val_obj:
                        val_obj = ApplicationFieldValue.objects.create(
                            application=app, 
                            field=field,
                            field_label=field.label,
                            field_type=field.field_type
                        )
                    
                    val_obj.value = file_obj.name # Or save actual file
                    val_obj.save()
            else:
                val = request.POST.get(key)
                if val is not None:
                    # FIX: Handle potential duplicate values safely
                    val_qs = ApplicationFieldValue.objects.filter(application=app, field=field)
                    if val_qs.exists():
                        val_qs.update(value=val, field_label=field.label, field_type=field.field_type)
                    else:
                        ApplicationFieldValue.objects.create(
                            application=app, 
                            field=field, 
                            field_label=field.label,
                            field_type=field.field_type,
                            value=val
                        )
        
        # 3. Save Qualifying Exam Marks
        # Only target fields in the 'Qualifying Examination' section
        qe_field = FormField.objects.filter(
            form=course.form, 
            section__name__icontains="Qualifying Examination"
        ).first()
        if qe_field:
            # Delete old marks for this field before re-saving
            ApplicationFieldValue.objects.filter(application=app, field=qe_field, value__contains=":").delete()
            for key in request.POST:
                if key.startswith("subject_"):
                    subject_name = key.replace("subject_", "").strip()
                    marks = request.POST.get(key)
                    if marks:
                        ApplicationFieldValue.objects.create(
                            application=app,
                            field=qe_field,
                            value=f"{subject_name}:{marks}:100"
                        )
        
        
        messages.success(request, f"Student {app.student.first_name} has been successfully registered! Admission No: {adm.register_number}")
        
        # SEND NOTIFICATION EMAIL
        send_admission_email(adm)
        
        return redirect('student_list')

    # GET Request
    student_name = get_student_name(app)
    
    # Auto-generate Registration ID
    course_code = course.course_code or "GEN"
    last_adm = Admission.objects.filter(registration_id__startswith=course_code).order_by('-id').first()
    if last_adm:
        import re
        nums = re.findall(r'\d+', last_adm.registration_id)
        registration_id = f"{course_code}{int(nums[-1])+1:05d}" if nums else f"{course_code}00001"
    else:
        registration_id = f"{course_code}00001"
        
    fee_categories = FeeCategory.objects.filter(course=course)
    fee_cats_json = []
    for cat in fee_categories:
        fee_cats_json.append({
            'id': cat.id, 'name': cat.name, 'total': float(cat.total_fee), 
            'breakdown': cat.breakdown, 'type': cat.category_type
        })
    
    # Fetch Dynamic Fields for the specific course form
    form_fields = FormField.objects.filter(form=course.form).order_by('section__order', 'order')
    sections = {}
    for f in form_fields:
        if f.section not in sections:
            sections[f.section] = []
        sections[f.section].append(f)
    
    # Fetch existing values for these fields
    field_values = {v.field_id: v.value for v in app.field_values.all()}
    for f in form_fields:
        f.current_value = field_values.get(f.id, "")
        # FIX: Ensure Full Name shows student name, not corrupted subject marks
        if f.label == "Full Name" and (not f.current_value or ":" in str(f.current_value)):
            f.current_value = app.student.first_name
        f.value = f.current_value  # Support templates using .value or .current_value

    # Fetch marks for display
    subjects = []
    latest_subjects = {}
    for v in app.field_values.all().order_by('-id'):
        if v.value and ":" in str(v.value) and not v.field.is_photo and not v.field.is_signature:
            parts = str(v.value).split(":")
            if len(parts) >= 2:
                name = parts[0].strip()
                marks = parts[1].strip()
                if name not in latest_subjects:
                    latest_subjects[name] = marks
    for name, marks in latest_subjects.items():
        subjects.append({"name": name, "marks": marks})

    # Get subcategories (labels) for the course category
    subcategories = course.category.subcategories.all() if course.category else []

    return render(request, 'institute/register_student.html', {
        'app': app,
        'student_name': student_name,
        'registration_id': registration_id,
        'fee_categories': fee_categories,
        'fee_cats_json': json.dumps(fee_cats_json),
        'sections': sections,
        'subjects': subjects,
        'subcategories': subcategories,
        'academic_years': AcademicYear.objects.filter(institute=app.institute),
        'courses': Course.objects.filter(institute=app.institute)
    })


from django.http import JsonResponse

# ✅ AJAX: LOAD SUBCATEGORIES
def load_subcategories(request):
    course_id = request.GET.get('course_id')
    subcategories = CourseSubCategory.objects.filter(category__courses__id=course_id)
    data = [{'id': s.id, 'name': s.name} for s in subcategories]
    return JsonResponse(data, safe=False)


# ✅ AJAX: LOAD CLASSES
def load_classes(request):
    course_id = request.GET.get('course_id')
    academic_year_id = request.GET.get('academic_year_id')
    period_id = request.GET.get('period_id')
    category_id = request.GET.get('category_id') # New filter
    
    classes = Class.objects.filter(institute=request.user.institute)
    
    if course_id:
        classes = classes.filter(course_id=course_id)
    
    # Optional filters: If these exist on the class, they should match. 
    # But if the class has NO year/period assigned, it should still show up.
    # OR, if we want to show all classes for the course regardless of year/period for flexibility:
    
    # For now, let's keep it course-focused as requested by the user to "show my classes"
    # if academic_year_id:
    #     classes = classes.filter(academic_year_id=academic_year_id)
    # if period_id:
    #     classes = classes.filter(period_id=period_id)
        
    data = [{'id': c.id, 'name': c.name} for c in classes]
    return JsonResponse(data, safe=False)


# ✅ AJAX: LOAD FORM FIELDS
def load_form_fields(request):
    course_id = request.GET.get('course_id')
    course = get_object_or_404(Course, id=course_id)
    fields = FormField.objects.filter(form=course.form).order_by('section__order', 'order')
    
    data = []
    for f in fields:
        data.append({
            'id': f.id,
            'label': f.label,
            'type': f.field_type,
            'required': f.required,
            'section': f.section.name if f.section else 'General Info',
            'options': [{'value': o.value, 'text': o.display_text} for o in f.options.all()] if f.field_type == 'select' else []
        })
    return JsonResponse(data, safe=False)


def load_exam_subjects(request):
    course_id = request.GET.get('course_id')
    course = get_object_or_404(Course, id=course_id)
    
    # 1. Find the qualifying exam field in the course's form
    # We look for a field with 'exam' in the label as per ranking logic
    exam_field = FormField.objects.filter(form__course=course, label__icontains="exam").first()
    
    if not exam_field:
        return JsonResponse([], safe=False)
        
    # 2. Get the subjects for the exams configured in this field (if it's a select)
    # For simplicity, we fetch all unique exams associated with this course's category or similar
    # But usually, there's a specific 'QualifyingExam' model.
    # The simplest way is to return subjects for ALL exams if no specific one is locked,
    # or let the user choose the exam first.
    
    subjects_data = []
    # If the user selected an exam in the form, we could narrow it down.
    # For now, return subjects for the first QualifyingExam found or all.
    exams = QualifyingExam.objects.all()
    for ex in exams:
        for sub in ex.subjects.all():
            subjects_data.append({
                'exam_id': ex.id,
                'exam_name': ex.name,
                'subject_id': sub.id,
                'subject_name': sub.name,
                'max_marks': sub.max_marks
            })
            
    return JsonResponse(subjects_data, safe=False)


# =========================
# MANUAL REGISTRATION
# =========================
@login_required
def register_manual(request):
    if request.method == 'POST':
        # 1. Create a dummy / actual Student User
        student_name = request.POST.get('student_name')
        mobile = request.POST.get('mobile')
        email = request.POST.get('email')
        
        # Check if user exists
        user, created = User.objects.get_or_create(
            username=mobile,
            defaults={
                'email': email,
                'role': 'student',
                'first_name': student_name
            }
        )
        if created:
            user.set_password('jdt123') # Default password
            user.save()

        registration_id = request.POST.get('registration_id')
        if Admission.objects.filter(registration_id=registration_id).exists():
            messages.error(request, f"Registration ID {registration_id} is already in use. Please use a unique ID.")
            return redirect('register_manual')

        # 2. Create Application
        institute = request.user.institute
        course_id = request.POST.get('course_id')
        academic_year_id = request.POST.get('academic_year_id')
        
        application = Application.objects.create(
            student=user,
            institute=institute,
            academic_year_id=academic_year_id,
            course_id=course_id,
            status='selected' # Manual registration usually means they are already selected
        )

        # 3. Save Form Fields (Similar to apply_course)
        fields = FormField.objects.filter(form__course_id=course_id)
        for field in fields:
            key = f'field_{field.id}'
            if field.field_type == 'file':
                file_obj = request.FILES.get(key)
                if file_obj:
                    fs = FileSystemStorage()
                    filename = fs.save(file_obj.name, file_obj)
                    ApplicationFieldValue.objects.create(
                        application=application, 
                        field=field,
                        field_label=field.label,
                        field_type=field.field_type,
                        value=filename
                    )
            else:
                value = request.POST.get(key)
                if value:
                    ApplicationFieldValue.objects.create(
                        application=application, 
                        field=field,
                        field_label=field.label,
                        field_type=field.field_type,
                        value=value
                    )

        # 4. Save Subjects for Meriting/Ranking
        # Link subjects to the 'Qualifying Examination' field if it exists
        qe_field = FormField.objects.filter(form__course_id=course_id, section__name__icontains="Qualifying Examination").first()
        if not qe_field:
            qe_field = fields.first()
            
        if qe_field:
            for key in request.POST:
                if key.startswith("subject_"):
                    subject_name = key.replace("subject_", "").strip()
                    marks = request.POST.get(key)
                    if marks:
                        ApplicationFieldValue.objects.create(
                            application=application,
                            field=qe_field, 
                            value=f"{subject_name}:{marks}:100" # Default max 100 for manual entries
                        )

        # 5. Create Admission
        registration_id = request.POST.get('registration_id')
        date_of_join = request.POST.get('date_of_join')
        fee_cat_id = request.POST.get('fee_category_id')
        joining_period_id = request.POST.get('joining_period_id')
        calculated_fee = request.POST.get('calculated_fee')
        discount_amount = request.POST.get('discount_amount', 0) or 0
        discount_reason = request.POST.get('discount_reason')
        final_fee = request.POST.get('final_fee')
        
        care_of = request.POST.get('care_of')
        guardian_name = request.POST.get('guardian_name')
        guardian_mobile = request.POST.get('guardian_mobile')
        relationship = request.POST.get('relationship')
        guardian_address = request.POST.get('guardian_address')

        # Fix: Convert date string to date object
        doj_obj = datetime.datetime.strptime(date_of_join, '%Y-%m-%d').date() if date_of_join else datetime.date.today()

        adm = Admission.objects.create(
            application=application,
            registration_id=registration_id,
            date_of_join=doj_obj,
            selected_course_id=course_id,
            fee_category_id=fee_cat_id,
            joining_period_id=joining_period_id if joining_period_id else None,
            assigned_class_id=request.POST.get('assigned_class_id') if request.POST.get('assigned_class_id') else None,
            calculated_fee=calculated_fee,
            discount_amount=discount_amount,
            discount_reason=discount_reason,
            final_fee=final_fee,
            care_of=care_of,
            guardian_name=guardian_name,
            guardian_mobile=guardian_mobile,
            relationship=relationship,
            guardian_address=guardian_address
        )
        
        
        messages.success(request, f"Manual admission completed for {student_name}! Admission No: {adm.register_number}")
        
        # SEND NOTIFICATION EMAIL
        send_admission_email(adm)
        
        return redirect('student_list')
    institutes = [request.user.institute]
    academic_years = AcademicYear.objects.all()
    courses = Course.objects.filter(institute=request.user.institute)
    
    return render(request, 'institute/register_manual.html', {
        'institutes': institutes,
        'academic_years': academic_years,
        'courses': courses,
        'fee_categories': FeeCategory.objects.filter(course__institute=request.user.institute),
        # For manual registration, we might need to load form fields via AJAX (already handled in template)
    })


# =========================
# LOGIN
# =========================
def institute_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(username=username, password=password)

        if user:

            if user.role != 'institute':
                messages.error(request, "Not an institute account")
                return redirect('/institute/login/')

            if not hasattr(user, 'institute'):
                messages.error(request, "Institute not assigned")
                return redirect('/institute/login/')

            login(request, user)
            return redirect('/institute/dashboard/')

        else:
            messages.error(request, "Invalid username or password")

    return render(request, 'institute/login.html')


# =========================
# GENERATE PDF
# =========================




# =========================
# DOWNLOAD PDF
# =========================
def download_application_zip(request, app_id):

    application = Application.objects.get(id=app_id)

    # 🔥 Create ZIP in memory
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:

        # ===== PDF =====
        pdf_buffer = BytesIO()
        generate_application_pdf(application, pdf_buffer)

        pdf_filename = f"application_{application.id}.pdf"
        zip_file.writestr(pdf_filename, pdf_buffer.getvalue())

        # ===== FILES =====
        for v in application.field_values.all():

            if v.field.field_type == "file" and v.value:

                file_path = os.path.join(settings.MEDIA_ROOT, str(v.value))
                if os.path.exists(file_path):
                     with open(file_path, 'rb') as f:
                         filename = os.path.basename(file_path)
                         # Add prefix to distinguish files
                         label_slug = v.field.label.replace(" ", "_").lower()
                         zip_file.writestr(f"documents/{label_slug}_{filename}", f.read())


    zip_buffer.seek(0)

    student_name = get_student_name(application).replace(" ", "_")

    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename={student_name}_Form_{application.id}.zip'

    return response


@login_required
def view_application(request, app_id):
    """
    Read-only view for the admission form.
    Accessible by the student who owns it or the institute staff.
    """
    if request.user.role == 'institute':
        # Ensure institute user is only viewing applications for their institute
        application = get_object_or_404(Application, id=app_id, institute=request.user.institute)
    else:
        # Students can only view their own applications
        application = get_object_or_404(Application, id=app_id, student=request.user)

    # Fetch field values with related field and section for efficient regrouping
    field_values = application.field_values.select_related('field', 'field__section').order_by('field__section__order', 'field__order')

    # Identify photo and signature
    student_photo = None
    student_signature = None

    # We also need to separate normal fields from subject marks
    normal_fields = []
    subject_marks = []
    total_obtained = 0
    total_max = 0

    for fv in field_values:
        label_lower = fv.field.label.lower() if fv.field else (fv.field_label.lower() if fv.field_label else "")
        
        # Check for photo and signature
        is_media = False
        if (fv.field and fv.field.is_photo) or "photo" in label_lower or "passport" in label_lower:
            student_photo = fv.value
            is_media = True
        elif (fv.field and fv.field.is_signature) or "signature" in label_lower:
            student_signature = fv.value
            is_media = True
        
        # Determine if this value is a subject mark
        label = fv.field.label if fv.field else fv.field_label
        if fv.value and ":" in str(fv.value) and not is_media:
            try:
                parts = str(fv.value).split(":")
                name = parts[0]
                marks = parts[1]
                
                # Check for 3 parts (Name:Marks:Max)
                max_val = 100
                if len(parts) >= 3:
                     max_val = float(parts[2])
                
                marks_val = float(marks)
                total_obtained += marks_val
                total_max += max_val
                
                subject_marks.append({'name': name, 'marks': marks_val, 'max': max_val})
            except (ValueError, IndexError):
                if not is_media:
                    normal_fields.append(fv)
        else:
            if not is_media:
                # Robust ID-to-Name resolution for Qualifying Examination
                val = str(fv.value).strip()
                label_orig = fv.field.label if fv.field else (fv.field_label if fv.field_label else "")
                
                if label_orig == "Full Name" and (not val or ":" in val):
                    fv.value = application.student.first_name
                elif fv.field and ("exam" in label_lower or "qualifying" in label_lower):
                    if val.isdigit() or (val.lower().startswith('id:') and val[3:].strip().isdigit()):
                        clean_id = val[3:].strip() if val.lower().startswith('id:') else val
                        from academics.models import QualifyingExam
                        exam_obj = QualifyingExam.objects.filter(id=clean_id).first()
                        if exam_obj:
                            fv.value = exam_obj.name
                normal_fields.append(fv)

    percentage = (total_obtained / total_max * 100) if total_max > 0 else 0

    context = {
        'application': application,
        'app': application, 
        'field_values': normal_fields, 
        'subject_marks': subject_marks,
        'total_obtained': total_obtained,
        'total_max': total_max,
        'percentage': round(percentage, 2),
        'photo': student_photo,
        'signature': student_signature,
        'MEDIA_URL': settings.MEDIA_URL if hasattr(settings, 'MEDIA_URL') else getattr(settings, 'MEDIA_URL', '/media/'),
        'print_date': datetime.datetime.now().strftime('%d/%m/%Y %H:%M'),
    }

    return render(request, 'applications/view_application.html', context)


# # =========================
# def view_application(request, app_id):
#     application = get_object_or_404(Application, id=app_id)
#     institute = application.course.institute if application.course else None
    
#     # Efficiently fetch field values
#     field_values = application.field_values.select_related('field', 'field__section').order_by('field__section__order', 'field__order')
    
#     student_photo = None
#     student_signature = None
#     normal_fields = []
#     subject_marks = []
    
#     for fv in field_values:
#         label_lower = fv.field.label.lower()
        
#         # Check for photo and signature specifically using field flags or label keywords
#         if fv.field.is_photo or "photo" in label_lower or "passport" in label_lower:
#             student_photo = fv.value
#         if fv.field.is_signature or "signature" in label_lower:
#             student_signature = fv.value
            
#         # Subject marks handling: Support both "Subj:Marks" and "Subj:Marks:Max"
#         if fv.value and ":" in str(fv.value) and not fv.field.is_photo and not fv.field.is_signature:
#             parts = str(fv.value).split(":")
#             if len(parts) >= 2:
#                 subject_marks.append({
#                     'subject': parts[0].strip(),
#                     'marks': parts[1].strip(),
#                     'max': parts[2].strip() if len(parts) > 2 else "100"
#                 })
#         else:
#             normal_fields.append(fv)

#     return render(request, 'institute/view_application.html', {
#         'app': application,
#         'institute': institute,
#         'field_values': normal_fields, 
#         'subject_marks': subject_marks,
#         'photo': student_photo,
#         'signature': student_signature,
#         'MEDIA_URL': settings.get('MEDIA_URL', '/media/') if hasattr(settings, 'get') else getattr(settings, 'MEDIA_URL', '/media/'),
#         'print_date': datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
#     })

# =========================
# RANKLIST 
# =========================

def calculate_total_and_percentage(application):
    total = 0
    max_total = 0
    main_subject_marks = 0
    sub_subject_marks = 0

    # Robust Exam Identification
    exam_id = None
    for v in application.field_values.all():
        if v.field and "exam" in v.field.label.lower():
            # v.value could be an ID (integer) or a string name
            val = str(v.value).strip()
            if val.isdigit():
                exam_id = int(val)
            else:
                # Try finding by name if it's a string
                ex_obj = QualifyingExam.objects.filter(name__iexact=val).first()
                if ex_obj:
                    exam_id = ex_obj.id
            if exam_id:
                break

    subjects_config = {}
    if exam_id:
        subjects = ExamSubject.objects.filter(exam_id=exam_id)
        for s in subjects:
            subjects_config[s.name.lower()] = {
                "include": s.include_in_rank,
                "main": s.is_main_subject,
                "sub": s.is_sub_subject,
                "max": s.max_marks
            }

    # calculate
    for fv in application.field_values.all():
        val_str = str(fv.value or "").strip()
        if ":" in val_str:
            try:
                # Minimal fix to handle Name:Marks:Max format
                parts = val_str.split(":")
                subject = parts[0].lower().strip()
                mark_val = float(parts[1].strip())

                config = subjects_config.get(subject)
                if config and config["include"]:
                    total += mark_val
                    max_total += config["max"]

                    # main subject for tie
                    if config["main"]:
                        main_subject_marks = max(main_subject_marks, mark_val)
                    
                    # sub subject for secondary tie
                    if config["sub"]:
                        sub_subject_marks = max(sub_subject_marks, mark_val)

            except (ValueError, TypeError, IndexError):
                continue

    percentage = (total / max_total * 100) if max_total > 0 else 0
    return total, round(percentage, 2), main_subject_marks, sub_subject_marks

def rank_list_view(request):

    institute = request.user.institute
    course_id = request.GET.get('course')
    year_id = request.GET.get('year')
    

    applications = Application.objects.filter(institute=institute)

    if course_id:
        applications = applications.filter(course_id=course_id)

    if year_id:
        applications = applications.filter(academic_year_id=year_id)

    ranked_list = []

    for app in applications:
        total, percentage, main_mark, sub_mark = calculate_total_and_percentage(app)

        ranked_list.append({
            "app": app,
            "name": get_student_name(app),
            "course": app.course.name if app.course else "No Course",
            "total": total,
            "percentage": percentage,
            "main_mark": main_mark,
            "sub_mark": sub_mark
        })

    #  SORT DESCENDING
    ranked_list.sort(
        key=lambda x: (x['percentage'], x['main_mark'], x['sub_mark']),
        reverse=True
    )

    #  ASSIGN RANK
    for i, item in enumerate(ranked_list, start=1):
        item['rank'] = i

    context = {
        "ranked_list": ranked_list,
        "courses": Course.objects.filter(institute=institute),
        "years": AcademicYear.objects.all()
    }

    return render(request, "institute/rank_list.html", context)


# =========================
# EXPORT RANKLIST 
# =========================
def get_student_name(application):
    """
    Returns the student's name from the User model first_name, 
    falling back to dynamic field values, and finally username.
    """
    # 1. Check User model
    if application.student.first_name:
        return application.student.first_name

    # 2. Check for field marked as is_name_field
    for v in application.field_values.all():
        if v.field.is_name_field:
            return v.value
        
    # 3. Fallback to label search
    for v in application.field_values.all():
        label = v.field.label.lower()
        if "name" in label and ":" not in str(v.value):
            return v.value

    return application.student.username

def export_rank_excel(request):
    institute = request.user.institute
    course_id = request.GET.get('course')
    year_id = request.GET.get('year')

    applications = Application.objects.filter(institute=institute)

    if course_id:
        applications = applications.filter(course_id=course_id)

    if year_id:
        applications = applications.filter(academic_year_id=year_id)

    ranked_list = []

    for app in applications:
        total, percentage, main_mark = calculate_total_and_percentage(app)

        ranked_list.append({
            "name": get_student_name(app),
            "total": total,
            "course": app.course.name if app.course else "No Course",
            "percentage": percentage,
            "main_mark": main_mark
        })

    # SORT DESCENDING
    ranked_list.sort(
        key=lambda x: (x['total'], x['main_mark']),
        reverse=True
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Rank List"

    # HEADER
    ws.append(["Rank", "Name", "Course", "Total Score", "Percentage"])

    # DATA
    for i, item in enumerate(ranked_list, start=1):
        ws.append([
            i,
            item['name'],       
            item['course'],     
            item['total'],
            f"{item['percentage']}%"
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = 'attachment; filename=rank_list.xlsx'

    wb.save(response)

    return response

# =========================
# EXPORT STUDENT LIST
# =========================
@login_required
def excel_export_students(request):
    institute = getattr(request.user, 'institute', None)
    if not institute:
        return HttpResponse("Unauthorized", status=401)

    query = request.GET.get('q', '')
    course_filter = request.GET.get('course', '')
    year_filter = request.GET.get('year', '')
    status_filter = request.GET.get('status', '')

    admissions = Admission.objects.filter(application__institute=institute).select_related(
        'application', 'selected_course', 'application__academic_year', 'joining_period'
    ).prefetch_related(
        'application__field_values', 'application__field_values__field'
    ).order_by('-created_at')

    if query:
        admissions = admissions.filter(
            Q(register_number__icontains=query) |
            Q(application__id__icontains=query) |
            Q(application__field_values__value__icontains=query, application__field_values__field__is_name_field=True)
        ).distinct()

    if course_filter:
        admissions = admissions.filter(selected_course_id=course_filter)
    if year_filter:
        admissions = admissions.filter(application__academic_year_id=year_filter)
    if status_filter:
        admissions = admissions.filter(status=status_filter)

    wb = Workbook()
    ws = wb.active
    ws.title = "Student Inventory"

    headers = ["SL NO", "Register No", "Student Name", "Course", "Year/Period", "Admission Year", "Status"]
    ws.append(headers)

    for i, adm in enumerate(admissions, start=1):
        ws.append([
            i,
            adm.register_number,
            get_student_name(adm.application),
            adm.selected_course.name,
            adm.joining_period.name if adm.joining_period else "N/A",
            adm.application.academic_year.name if adm.application.academic_year else "N/A",
            adm.get_status_display()
        ])

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = f'attachment; filename=Students_Export_{datetime.datetime.now().strftime("%Y%m%d")}.xlsx'
    wb.save(response)
    return response

# =========================
# REGISTER
# =========================
def institute_register(request):
    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')
        institute_name = request.POST.get('institute_name')

        user = User.objects.create_user(
            username=username,
            password=password,
            role='institute'
        )

        institute = Institute.objects.create(
            user=user,
            name=institute_name,
            code=username.upper()
        )

        # link reverse
        user.institute = institute
        user.save()

        return redirect('/institute/login/')

    return render(request, 'institute/register.html')


# =========================
# DASHBOARD
# =========================
@login_required
def institute_dashboard(request):
    institute = getattr(request.user, 'institute', None)
    if not institute:
        return redirect('/institute/register/')

    # Support filtering and search
    query = request.GET.get('q', '')
    course_filter = request.GET.get('course', '')
    year_filter = request.GET.get('year', '')
    status_filter = request.GET.get('status', '')

    # Query applications for this institute (both pending-registration and admitted)
    apps = Application.objects.filter(institute=institute).select_related(
        'course', 'academic_year', 'admission'
    ).prefetch_related(
        'field_values', 'field_values__field'
    ).order_by('-created_at')

    if query:
        apps = apps.filter(
            Q(id__icontains=query) |
            Q(admission__register_number__icontains=query) |
            Q(field_values__value__icontains=query, field_values__field__is_name_field=True)
        ).distinct()

    if course_filter:
        apps = apps.filter(course_id=course_filter)
    if year_filter:
        apps = apps.filter(academic_year_id=year_filter)
    
    # Status filter is combined (Application status vs Admission status)
    if status_filter:
        if status_filter in ['active', 'warned', 'suspended', 'trashed']:
            apps = apps.filter(admission__status=status_filter)
        else:
            apps = apps.filter(status=status_filter)

    # Performance: Pagination
    paginator = Paginator(apps, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Process names and fields for display
    processed_admissions = []
    for app in page_obj:
        name = get_student_name(app)
        
        # Extract Contact, Caste, Gender, etc.
        contact = "-"
        gender = "-"
        caste = ""
        quota = ""
        remarks = ""

        # Optimized field extraction
        for v in app.field_values.all():
            lbl = v.field.label.lower()
            val = v.value
            
            if not val or val == "None": continue

            if "phone" in lbl or "mobile" in lbl or "contact" in lbl:
                contact = val
            elif "gender" in lbl:
                gender = val
            elif "caste" in lbl:
                caste = val
            elif "quota" in lbl:
                quota = val
            elif "remarks" in lbl or "comment" in lbl:
                remarks = val

        processed_admissions.append({
            'form_id': app.id,
            'student_name': name,
            'contact': contact,
            'gender': gender,
            'caste': caste,
            'quota': quota,
            'remarks': remarks,
            'status': app.status,
            'status_display': app.get_status_display(),
        })

    courses = Course.objects.filter(institute=institute)
    years = AcademicYear.objects.all()

    return render(request, 'institute/dashboard.html', {
        'page_obj': page_obj,
        'admissions': processed_admissions,
        'courses': courses,
        'years': years,
        'selected_course': course_filter,
        'selected_year': year_filter,
        'selected_status': status_filter,
        'query': query,
    })

# =========================
# STD NAME EXTRACT
# =========================
# Name extraction handled by the global helper function at line 842.




# =========================
# EDIT APPLICATION
# =========================
@login_required
def edit_application(request, app_id):

    app = get_object_or_404(Application, id=app_id)

    # =========================
    # GET FORM FIELDS
    # =========================
    fields = FormField.objects.filter(
        form=app.course.form
    ).select_related('section').order_by('section__order', 'order')

    # =========================
    # ATTACH VALUES TO FIELDS
    # =========================
    field_values = {v.field_id: v.value for v in app.field_values.all()}
    for f in fields:
        f.current_value = field_values.get(f.id, "")
        # FIX: Ensure Full Name shows student name, not corrupted subject marks
        if f.label == "Full Name" and (not f.current_value or ":" in str(f.current_value)):
            f.current_value = app.student.first_name
        f.value = f.current_value  # Support templates using .value or .current_value

    

    # =========================
    # SAVE (POST)
    # =========================
    if request.method == 'POST':

        #  UPDATE NORMAL FIELDS
        ApplicationFieldValue.objects.filter(
             application=app,
             value__contains=":"
              ).delete()


        for field in fields:    
            key = f'field_{field.id}'
            
        
            # FILE FIELD
            if field.field_type == 'file':
                file_obj = request.FILES.get(key)

                if file_obj:
                    ApplicationFieldValue.objects.update_or_create(
                        application=app,
                        field=field,
                        defaults={'value': file_obj.name}
                    )

            else:
                val = request.POST.get(key)

                if val is not None:
                    ApplicationFieldValue.objects.update_or_create(
                        application=app,
                        field=field,
                        defaults={'value': val}
                    )

        # =========================
        #  UPDATE SUBJECTS (FIXED)
        # =========================
        # =========================
        #  UPDATE SUBJECTS (Parsing correctly)
        # =========================
        # Delete only "marks" type values to replace them
        ApplicationFieldValue.objects.filter(
            application=app,
            value__contains=":"
        ).exclude(
            field__field_type='file' # Don't delete file values which might have colons (rare but possible)
        ).delete()

        # Only target fields in the 'Qualifying Examination' section
        qe_field = FormField.objects.filter(
            form=app.course.form, 
            section__name__icontains="Qualifying Examination"
        ).first()

        for key in request.POST:
            if key.startswith("subject_"):
                subject_name = key.replace("subject_", "").strip()
                marks = request.POST.get(key)
                if marks:
                    ApplicationFieldValue.objects.create(
                        application=app,
                        field=qe_field,  
                        value=f"{subject_name}:{marks}:100"
                    )

        # =========================
        # STATUS + REMARKS
        # =========================
        app.status = request.POST.get('status')
        app.remarks = request.POST.get('remarks')
        app.save()

        return redirect('/institute/dashboard/')

    # =========================
    #  LOAD SUBJECTS (FIXED)
    # =========================
    subjects = []
    latest_subjects = {}

    for v in app.field_values.all().order_by('-id'):
        if v.value and ":" in str(v.value) and not v.field.is_photo and not v.field.is_signature:
            parts = str(v.value).split(":")
            if len(parts) >= 2:
                name = parts[0].strip()
                marks = parts[1].strip()
                if name not in latest_subjects:
                    latest_subjects[name] = marks
            
    for name, marks in latest_subjects.items():
        subjects.append({
            "name": name,
            "marks": marks
        })
        
        

    # =========================
    # RENDER
    # =========================
    return render(request, 'institute/edit_application.html', {
        'app': app,
        'fields': fields,
        'subjects': subjects,
    })

# ✅ STUDENT STATUS UPDATE (AJAX)
@login_required
def update_student_status(request, admission_id):
    if request.method == 'POST':
        admission = get_object_or_404(Admission, id=admission_id, application__institute=request.user.institute)
        status = request.POST.get('status')
        reason = request.POST.get('reason') # Dashboard JS sends 'reason'

        if status:
            admission.status = status
            admission.status_reason = reason
            admission.save()
            return JsonResponse({'status': 'success', 'message': 'Status updated successfully'})
        
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


# ✅ EXCEL TEMPLATE DOWNLOAD
@login_required
def download_excel_template(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "Student Import Template"
    
    headers = [
        "Student Name (*)", "Mobile (*)", "Email (*)", "Registration ID (*)", 
        "Course Code (*)", "Academic Year (*)", "Date of Join (YYYY-MM-DD) (*)", 
        "Fee Category Name (*)", "Joining Period (Optional)", 
        "Guardian Name (*)", "Guardian Mobile (*)", "Relationship (*)", "Guardian Address (*)"
    ]
    
    # Add dynamic form fields as columns
    dynamic_fields = FormField.objects.filter(form__course__institute=request.user.institute).values_list('label', flat=True).distinct()
    for field_label in dynamic_fields:
        if field_label not in headers:
            headers.append(f"Field: {field_label}")

    ws.append(headers)
    
    # Adjust column widths
    for i, _ in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = 25

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="student_import_template.xlsx"'
    wb.save(response)
    return response


# ✅ EXCEL BULK IMPORT
@login_required
def excel_import_students(request):
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            return JsonResponse({'status': 'error', 'message': 'No file uploaded'}, status=400)

        try:
            wb = load_workbook(excel_file)
            ws = wb.active
            # Identify headers for dynamic fields
            headers = [cell.value for cell in ws[1]]
            field_cols = {}
            for i, header in enumerate(headers):
                if header and header.startswith("Field: "):
                    field_cols[header.replace("Field: ", "")] = i

            rows = list(ws.iter_rows(min_row=2, values_only=True))
            
            report = {'success': 0, 'errors': []}
            institute = request.user.institute

            for row_idx, row in enumerate(rows, 2):
                if not any(row): continue # Skip empty rows

                try:
                    # Unpack base fields (ensure we have enough columns)
                    if len(row) < 13:
                        report['errors'].append(f"Row {row_idx}: Insufficient columns.")
                        continue
                        
                    name, mobile, email, reg_id, c_code, a_year, doj, f_cat, period, g_name, g_mobile, rel, g_addr = row[:13]
                    
                    # Validation & Mapping
                    if not all([name, mobile, email, reg_id, c_code, a_year, doj, f_cat, g_name, g_mobile, rel, g_addr]):
                        report['errors'].append(f"Row {row_idx}: Missing mandatory fields.")
                        continue

                    # Unique Registration ID check
                    if Admission.objects.filter(registration_id=reg_id).exists():
                        report['errors'].append(f"Row {row_idx}: Registration ID '{reg_id}' already exists.")
                        continue

                    course = Course.objects.filter(institute=institute, course_code=c_code).first()
                    if not course:
                        report['errors'].append(f"Row {row_idx}: Course code '{c_code}' not found.")
                        continue

                    fee_cat = FeeCategory.objects.filter(institute=institute, name=f_cat).first()
                    if not fee_cat:
                        report['errors'].append(f"Row {row_idx}: Fee Category '{f_cat}' not found.")
                        continue
                    
                    year_obj = AcademicYear.objects.filter(name=a_year).first()
                    if not year_obj:
                        report['errors'].append(f"Row {row_idx}: Academic Year '{a_year}' not found.")
                        continue

                    # Create Records
                    user, _ = User.objects.get_or_create(
                        username=mobile,
                        defaults={'email': email, 'role': 'student', 'first_name': name}
                    )
                    
                    app = Application.objects.create(
                        student=user, institute=institute, academic_year=year_obj, course=course, status='selected'
                    )

                    # Save Dynamic Fields
                    form_fields = FormField.objects.filter(form__course=course)
                    for f in form_fields:
                        if f.label in field_cols:
                            val = row[field_cols[f.label]]
                            if val:
                                ApplicationFieldValue.objects.create(
                                    application=app,
                                    field=f,
                                    field_label=f.label,
                                    field_type=f.field_type,
                                    value=str(val)
                                )
                    
                    Admission.objects.create(
                        application=app, registration_id=reg_id, date_of_join=doj,
                        selected_course=course, fee_category=fee_cat,
                        calculated_fee=fee_cat.total_fee, final_fee=fee_cat.total_fee,
                        guardian_name=g_name, guardian_mobile=g_mobile,
                        relationship=rel, guardian_address=g_addr
                    )
                    report['success'] += 1

                except Exception as e:
                    report['errors'].append(f"Row {row_idx}: {str(e)}")

            return JsonResponse({'status': 'success', 'report': report})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f"Failed to process file: {str(e)}"}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


# ✅ LOGOUT (COMMON FOR ALL USERS )
def user_logout(request):
    logout(request)
    return redirect('institute_login')

# =========================
# STUDENT LIST & EXPORT
# =========================

@login_required
def student_list_view(request):
    institute = request.user.institute
    admissions = Admission.objects.filter(application__institute=institute).select_related('application__student', 'application__academic_year', 'application__course')

    # Filters
    form_id = request.GET.get('form_id') # Search by Admission No / Register Number
    name = request.GET.get('name')
    batch_id = request.GET.get('batch_id')
    course_id = request.GET.get('course_id')
    status_filter = request.GET.get('status')

    if form_id:
        admissions = admissions.filter(Q(register_number__icontains=form_id) | Q(registration_id__icontains=form_id))
    
    if name:
        admissions = admissions.filter(
            Q(application__student__first_name__icontains=name) | 
            Q(application__student__username__icontains=name)
        )

    if batch_id:
        admissions = admissions.filter(application__academic_year_id=batch_id)

    if course_id:
        admissions = admissions.filter(application__course_id=course_id)
        
    if status_filter:
        admissions = admissions.filter(status=status_filter)

    # Context data for filters
    batches = AcademicYear.objects.all()
    courses = Course.objects.filter(institute=institute)

    return render(request, 'institute/student_list.html', {
        'admissions': admissions,
        'batches': batches,
        'courses': courses,
        'admission_statuses': Admission.ADMISSION_STATUS
    })

@login_required
def update_student_status(request, admission_id):
    admission = get_object_or_404(Admission, id=admission_id, application__institute=request.user.institute)
    
    new_status = request.GET.get('status')
    reason = request.GET.get('reason', '')

    if new_status in dict(Admission.ADMISSION_STATUS):
        admission.status = new_status
        if reason:
            admission.status_reason = reason
        admission.save()
        messages.success(request, f"Status updated for {admission.application.student.first_name or admission.application.student.username}")
    
    return redirect('student_list')

@login_required
def export_students_excel(request):
    institute = request.user.institute
    admissions = Admission.objects.filter(application__institute=institute).select_related('application__student', 'application__academic_year', 'application__course', 'fee_category')

    # Apply same filters as list view
    form_id = request.GET.get('form_id')
    name = request.GET.get('name')
    batch_id = request.GET.get('batch_id')
    course_id = request.GET.get('course_id')

    if form_id:
        admissions = admissions.filter(Q(register_number__icontains=form_id) | Q(registration_id__icontains=form_id))
    if name:
        admissions = admissions.filter(application__student__first_name__icontains=name)
    if batch_id:
        admissions = admissions.filter(application__academic_year_id=batch_id)
    if course_id:
        admissions = admissions.filter(application__course_id=course_id)

    wb = Workbook()
    ws = wb.active
    ws.title = "Student Registry"

    headers = [
        "Admission No.", "Date of join", "Quota", "Full Name", "Academic Year", "Gender", "DOB",
        "Religion", "Caste/Community", "Category(SC/ST/OBC)", "Payment category", "Student E-mail",
        "Student Mobile No.", "Aadhar Card Number", "Course", "Division", "Class(Sem/Year)",
        # Address Details
        "Permanent House Name/No", "Permanent Location", "Permanent Post", "Permanent Pin Code", 
        "Permanent Nationality", "Permanent State", "Permanent District",
        "Communication House Name/No", "Communication Location", "Communication Post", 
        "Communication Pin Code", "Communication Nationality", "Communication State", "Communication District",
        # Family Details
        "Father Name", "Father Mobile No.", "Mother Name", "Mother Mobile", 
        "Guardian Name", "Guardian Mobile No.", "Relationship with child", "Guardian Address"
    ]
    ws.append(headers)

    def fuzzy_val(app, label_part):
        matched = ApplicationFieldValue.objects.filter(application=app, field__label__icontains=label_part).first()
        return matched.value if matched else ""

    for adm in admissions:
        app = adm.application
        row = [
            adm.register_number,
            adm.date_of_join.strftime('%Y-%m-%d') if adm.date_of_join else "",
            adm.fee_category.name if adm.fee_category else "",
            app.student.first_name,
            app.academic_year.name if app.academic_year else "",
            fuzzy_val(app, "Gender"),
            fuzzy_val(app, "DOB") or fuzzy_val(app, "Birth"),
            fuzzy_val(app, "Religion"),
            fuzzy_val(app, "Caste") or fuzzy_val(app, "Community"),
            fuzzy_val(app, "Category") or fuzzy_val(app, "Reservation"),
            adm.fee_category.name if adm.fee_category else "",
            app.student.email,
            app.student.username,
            fuzzy_val(app, "Aadhar"),
            adm.selected_course.name if adm.selected_course else app.course.name,
            fuzzy_val(app, "Division"),
            adm.joining_period.name if adm.joining_period else fuzzy_val(app, "Class"),
            # Permanent Address (Fuzzy Matching)
            fuzzy_val(app, "Permanent") and fuzzy_val(app, "House") or fuzzy_val(app, "Address"),
            fuzzy_val(app, "Permanent") and fuzzy_val(app, "Location"),
            fuzzy_val(app, "Permanent") and fuzzy_val(app, "Post"),
            fuzzy_val(app, "Permanent") and fuzzy_val(app, "Pin"),
            fuzzy_val(app, "Nationality"),
            fuzzy_val(app, "State"),
            fuzzy_val(app, "District"),
            # Communication Address
            fuzzy_val(app, "Communication") and fuzzy_val(app, "House"),
            fuzzy_val(app, "Communication") and fuzzy_val(app, "Location"),
            fuzzy_val(app, "Communication") and fuzzy_val(app, "Post"),
            fuzzy_val(app, "Communication") and fuzzy_val(app, "Pin"),
            fuzzy_val(app, "Nationality"),
            fuzzy_val(app, "State"),
            fuzzy_val(app, "District"),
            # Family
            fuzzy_val(app, "Father Name"),
            fuzzy_val(app, "Father Mobile"),
            fuzzy_val(app, "Mother Name"),
            fuzzy_val(app, "Mother Mobile"),
            adm.guardian_name,
            adm.guardian_mobile,
            adm.relationship,
            adm.guardian_address
        ]
        ws.append(row)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Students_{institute.name.replace(" ", "_")}.xlsx"'
    wb.save(response)
    return response
