from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage
from django.views.decorators.csrf import csrf_exempt
from .models import Application, Payment, ApplicationFieldValue, Admission
from core.utils import generate_application_pdf
import datetime
from io import BytesIO
from institutes.models import Institute, AcademicYear
from academics.models import Course, ApplicationForm, ExamSubject, FormField


@login_required
def dashboard(request):
    # Fetch active admission record
    admission = Admission.objects.filter(application__student=request.user, status='active').select_related('assigned_class', 'application__course').first()
    
    subjects = []
    if admission and admission.assigned_class:
        subjects = admission.assigned_class.subjects.all()
        
    # NEW: Fetch active notifications from Application Forms
    # We show notifications from any active form that belongs to the student's institute
    notifications = []
    active_forms = ApplicationForm.objects.filter(is_active=True).exclude(notification_message__isnull=True).exclude(notification_message='')
    for form in active_forms:
        notifications.append({
            'title': form.title,
            'message': form.notification_message
        })
        
    return render(request, 'student/dashboard.html', {
        'admission': admission,
        'subjects': subjects,
        'is_admitted': admission is not None,
        'notifications': notifications
    })


@login_required
def my_applications(request):
    apps = Application.objects.filter(student=request.user).select_related('course')
    return render(request, 'student/my_applications.html', {'apps': apps})

@login_required
def apply_course(request):
    institutes = Institute.objects.all()
    academic_years = AcademicYear.objects.all()
    active_year = AcademicYear.objects.filter(is_active=True).first()

    if request.method == 'POST':

        # =========================
        # CREATE APPLICATION
        # =========================
        institute = Institute.objects.get(id=request.POST.get('institute'))

        application = Application.objects.create(
            student=request.user,
            institute=institute,
            academic_year_id=request.POST.get('academic_year'),
            course_id=request.POST.get('course'),
            status='pending_payment'
        )

        # =========================
        # GET FORM FIELDS (FILTERED BY ACADEMIC YEAR)
        # =========================
        # =========================
        # 🧪 PRE-VALIDATE SUBJECTS
        # =========================
        subjects_to_save = []
        for key in request.POST:
            if key.startswith("subject_"):
                subject_name = key.replace("subject_", "")
                marks_str = request.POST.get(key)
                
                if marks_str:
                    try:
                        marks_val = float(marks_str)
                        from academics.models import ExamSubject
                        subj_obj = ExamSubject.objects.filter(name=subject_name).first()
                        
                        max_val = subj_obj.max_marks if subj_obj else 100
                        pass_val = subj_obj.pass_mark if subj_obj else 0
                        
                        if marks_val > max_val or marks_val < pass_val:
                            from django.contrib import messages
                            # messages.error(request, f"Invalid marks for {subject_name.replace('_', ' ')}. Must be between {pass_val} and {max_val}.")
                            return redirect('/apply/')
                            
                        subjects_to_save.append({
                            'name': subject_name,
                            'marks': marks_val,
                            'max': max_val
                        })
                    except (ValueError, TypeError):
                        continue

        # =========================
        # SAVE CUSTOM FIELDS
        # =========================
        course_id = request.POST.get('course')
        from academics.models import ApplicationForm, FormField
        form_obj = ApplicationForm.objects.get(course_id=course_id)
        fields = form_obj.fields.all()

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

        # =========================
        # SAVE VALIDATED SUBJECTS
        # =========================
        # Link subjects to the 'Qualifying Examination' field if it exists
        qe_field = FormField.objects.filter(section__name="Qualifying Examination").first()
        for sub in subjects_to_save:
            ApplicationFieldValue.objects.create(
                application=application,
                field=qe_field,
                value=f"{sub['name']}:{sub['marks']}:{sub['max']}"
            )

        # =========================
        # PAYMENT INITIATION
        # =========================
        payment = Payment.objects.create(
            application=application,
            amount=form_obj.registration_fee,
            gateway_config=form_obj.payment_config
        )

        return redirect(f'/payment/{application.id}/')

    return render(request, 'student/form.html', {
        'institutes': institutes,
        'academic_years': academic_years,
        'active_year': active_year
    })
@login_required
def payment_page(request, app_id):
    from .payment_handlers import CCAvenueHandler, PhiCommerceHandler
    
    application = get_object_or_404(Application, id=app_id, student=request.user)
    try:
        payment = Payment.objects.get(application=application)
    except Payment.DoesNotExist:
        messages.error(request, "Payment information not found for this application.")
        return redirect('/my-applications/')
    
    config = payment.gateway_config
    
    if request.method == 'POST' and config:
        # User clicked "Pay Now"
        if config.gateway_type == 'ccavenue':
            handler = CCAvenueHandler(config)
            data = handler.initiate_payment(payment, request)
            return render(request, 'student/ccavenue_redirect.html', data)
            
        elif config.gateway_type == 'phicommerce':
            handler = PhiCommerceHandler(config)
            data = handler.initiate_payment(payment, request)
            
            if "error" in data:
                messages.error(request, f"Payment initiation failed: {data['error']}")
                return redirect(f'/payment/{app_id}/')
            
            # Save raw request/txn_id for tracking (merchantTxnNo)
            payment.gateway_transaction_id = data.get('txn_id')
            payment.save()
            
            return redirect(data['action_url'])

    return render(request, 'student/payment.html', {
        'application': application,
        'payment': payment,
        'config': config
    })


@login_required
def ccavenue_callback(request):
    from .payment_handlers import CCAvenueHandler
    # We don't have app_id in URL, but we have order_id (which is payment.id) in encResp
    # Need a dummy config to start decryption or get it from first active config
    from .models import PaymentConfig
    config = PaymentConfig.objects.filter(gateway_type='ccavenue', is_active=True).first()
    
    if not config:
        messages.error(request, "Payment configuration not found.")
        return redirect('/my-applications/')
        
    handler = CCAvenueHandler(config)
    result = handler.verify_payment(request.POST)
    
    # Tracking
    raw_response = result.get('raw', {})
    order_id = raw_response.get('order_id')
    
    if order_id:
        payment = Payment.objects.get(id=order_id)
        payment.gateway_response = raw_response
        payment.gateway_transaction_id = result.get('txn_id')
        
        if result['status'] == 'success':
            payment.status = 'success'
            payment.save()
            
            application = payment.application
            application.status = 'submitted'
            application.save()
            messages.success(request, "Payment successful!")
        else:
            payment.status = 'failed'
            payment.save()
            messages.error(request, "Payment failed.")
            
    return redirect('/my-applications/')


@csrf_exempt
def phicommerce_callback(request):
    from .payment_handlers import PhiCommerceHandler
    from .models import PaymentConfig
    
    # PayPhi redirects back with params in POST or GET
    data = request.POST if request.method == 'POST' else request.GET
    
    config = PaymentConfig.objects.filter(gateway_type='phicommerce', is_active=True).first()
    if not config:
        messages.error(request, "Payment configuration not found.")
        return redirect('/my-applications/')
         
    handler = PhiCommerceHandler(config)
    result = handler.verify_payment(data)
    
    if result['status'] == 'success':
        merchant_txn_no = result.get('merchant_txn_no', '')
        try:
            payment = Payment.objects.get(gateway_transaction_id=merchant_txn_no)
            
            # Update only if not already processed by webhook
            if payment.status == 'pending':
                payment.gateway_response = result.get('raw')
                payment.gateway_transaction_id = result.get('txn_id') # Update with bank ref
                payment.status = 'success'
                payment.save()
                
                application = payment.application
                application.status = 'submitted'
                application.save()
                messages.success(request, "Payment successful! Your application has been submitted.")
            else:
                messages.success(request, "Payment successful! Your application has been submitted.")
                
        except Payment.DoesNotExist:
            messages.error(request, "Transaction record not found.")
    else:
        messages.error(request, f"Payment failed: {result.get('error', 'Unknown error')}")

    return redirect('/my-applications/')


@csrf_exempt
def phicommerce_webhook(request):
    """
    S2S Webhook for PayPhi (Advice URL).
    PayPhi posts the transaction status here directly.
    """
    from .payment_handlers import PhiCommerceHandler
    from .models import PaymentConfig
    
    if request.method != 'POST':
        return HttpResponse("Method not allowed", status=405)
        
    data = request.POST
    config = PaymentConfig.objects.filter(gateway_type='phicommerce', is_active=True).first()
    
    if not config:
        return HttpResponse("Config not found", status=404)
        
    handler = PhiCommerceHandler(config)
    result = handler.verify_payment(data)
    
    if result['status'] == 'success':
        merchant_txn_no = result.get('merchant_txn_no', '')
        try:
            payment = Payment.objects.get(gateway_transaction_id=merchant_txn_no)
            
            # Background update
            if payment.status == 'pending':
                payment.gateway_response = result.get('raw')
                payment.status = 'success'
                payment.save()
                
                application = payment.application
                application.status = 'submitted'
                application.save()
                
            return HttpResponse("OK") # Standard acknowledgment
        except Payment.DoesNotExist:
            return HttpResponse("Transaction not found", status=404)
        except Exception:
            return HttpResponse("Error", status=500)
            
    return HttpResponse("Invalid Request", status=400)


@login_required
def payment_success(request, app_id):
    # This is now just a manual fallback or logic for 'none' gateway
    application = get_object_or_404(Application, id=app_id, student=request.user)
    payment = Payment.objects.get(application=application)

    if not payment.gateway_config:
        if payment.amount > 0:
            messages.error(request, "Payment gateway is not configured for this course. Please contact the administrator.")
            return redirect(f'/payment/{app_id}/')
            
        payment.status = 'success'
        payment.save()

        application.status = 'submitted'
        application.save()

        messages.success(request, "Application submitted successfully!")
    
    return redirect('/my-applications/')


# =========================
# AJAX
# =========================
def load_academic_years(request):
    institute_id = request.GET.get('institute_id')
    # Fetch years that have active application forms in this institute
    year_ids = ApplicationForm.objects.filter(
        course__institute_id=institute_id, 
        is_active=True
    ).values_list('academic_year_id', flat=True).distinct()
    
    years = AcademicYear.objects.filter(id__in=year_ids).values('id', 'name')
    return JsonResponse(list(years), safe=False)


def load_courses(request):
    institute_id = request.GET.get('institute_id')
    year_id = request.GET.get('academic_year_id')
    
    filters = {
        'institute_id': institute_id,
        'form__is_active': True
    }
    
    if year_id:
        filters['form__academic_year_id'] = year_id
        
    courses = Course.objects.filter(**filters).values('id', 'name')
    return JsonResponse(list(courses), safe=False)


def load_form_fields(request):
    course_id = request.GET.get('course_id')

    form = ApplicationForm.objects.filter(course_id=course_id,is_active=True).first()

    if not form:
        return JsonResponse([], safe=False)

    data = []

    for field in form.fields.select_related('section').prefetch_related('options'):
        data.append({
            'id': field.id,
            'label': field.label,
            'type': field.field_type,
            'section': field.section.name,
            'is_photo': field.is_photo,
            'is_signature': field.is_signature,
            'options': [
                {'value': opt.value, 'text': opt.display_text}
                for opt in field.options.all()
            ],
        })

    return JsonResponse(data, safe=False)


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
                # NEW: Resolve Display Text for Select/Dropdown fields
                val = str(fv.value).strip()
                fv.display_value = val
                if fv.field and fv.field.field_type in ['select', 'radio', 'checkbox']:
                    from academics.models import FieldOption
                    opt = FieldOption.objects.filter(field=fv.field, value=val).first()
                    if opt:
                        fv.display_value = opt.display_text
                
                # Robust ID-to-Name resolution for Qualifying Examination
                label_orig = fv.field.label if fv.field else (fv.field_label if fv.field_label else "")
                if label_orig == "Full Name" and (not val or ":" in val):
                    fv.value = application.student.first_name
                    fv.display_value = application.student.first_name
                elif fv.field and ("exam" in label_lower or "qualifying" in label_lower):
                    if val.isdigit() or (val.lower().startswith('id:') and val[3:].strip().isdigit()):
                        clean_id = val[3:].strip() if val.lower().startswith('id:') else val
                        from academics.models import QualifyingExam
                        exam_obj = QualifyingExam.objects.filter(id=clean_id).first()
                        if exam_obj:
                            fv.value = exam_obj.name
                            fv.display_value = exam_obj.name
                
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


@login_required
def download_application_pdf(request, app_id):
    """
    Downloads the individual application form as a PDF for the student.
    """
    application = get_object_or_404(Application, id=app_id, student=request.user)
    
    buffer = BytesIO()
    generate_application_pdf(application, buffer)
    buffer.seek(0)
    
    filename = f"Application_{application.id}.pdf"
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


def load_exam_subjects(request):
    exam_id = request.GET.get('exam_id')

    subjects = ExamSubject.objects.filter(exam_id=exam_id)

    data = [
        {'name': sub.name, 'max_marks': sub.max_marks, 'pass_mark': sub.pass_mark}
        for sub in subjects
    ]

    return JsonResponse(data, safe=False)