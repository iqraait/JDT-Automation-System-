from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.db.models import Q
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
from academics.models import Course, ApplicationForm, ExamSubject, FormField, NoticeBoard, Timetable, AcademicResult, StudentDocument, ApplicationFeeType, QualifyingExam


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
        
    # Fetch Notice Board Announcements (Guaranteed list for all logged-in users)
    notices = list(NoticeBoard.objects.filter(is_active=True).order_by('-created_at')[:10])

    # Calculate Attendance & Fee summary metrics for dashboard UI
    from academics.models import StudentAttendance, StudentFeePayment, FeeHead
    
    total_days = StudentAttendance.objects.filter(admission=admission).count() if admission else 0
    present_days = StudentAttendance.objects.filter(admission=admission, status='present').count() if admission else 0
    half_days = StudentAttendance.objects.filter(admission=admission, status='half_day').count() if admission else 0
    
    attendance_pct = round(((present_days + 0.5 * half_days) / total_days * 100), 1) if total_days > 0 else 0

    payments = StudentFeePayment.objects.filter(admission=admission, is_cancelled=False) if admission else []
    total_paid = sum(p.amount_paid for p in payments)
    fee_heads = FeeHead.objects.filter(fee_structure__course=admission.application.course, is_active=True) if (admission and admission.application and admission.application.course) else []
    total_tagged_fees = sum(fh.amount for fh in fee_heads)
    fee_balance = max(0, total_tagged_fees - total_paid)

    is_verified_or_enrolled = admission is not None

    return render(request, 'student/dashboard.html', {
        'admission': admission,
        'subjects': subjects,
        'is_admitted': is_verified_or_enrolled,
        'is_verified_or_enrolled': is_verified_or_enrolled,
        'notifications': notifications,
        'notices': notices,
        'total_days': total_days,
        'attendance_percentage': attendance_pct,
        'fee_balance': fee_balance,
        'total_paid': total_paid,
        'total_tagged_fees': total_tagged_fees,
    })


@login_required
def student_attendance(request):
    admission = Admission.objects.filter(application__student=request.user, status='active').select_related('assigned_class', 'application__course', 'application__institute').first()
    if not admission:
        messages.warning(request, "Attendance module is only available for enrolled students.")
        return redirect('student_dashboard')
    
    from academics.models import StudentAttendance
    attendances = list(StudentAttendance.objects.filter(admission=admission).order_by('-date')) if admission else []
    
    total_days = len(attendances)
    present_count = sum(1 for a in attendances if a.status == 'present')
    absent_count = sum(1 for a in attendances if a.status == 'absent')
    half_day_count = sum(1 for a in attendances if a.status == 'half_day')
    
    calc_percent = round(((present_count + 0.5 * half_day_count) / total_days * 100), 1) if total_days > 0 else 0

    import calendar
    year = int(request.GET.get('year', datetime.date.today().year))
    month = int(request.GET.get('month', datetime.date.today().month))
    
    cal = calendar.Calendar(firstweekday=6)
    month_days_raw = cal.monthdatescalendar(year, month)
    
    att_by_date = {a.date.strftime('%Y-%m-%d'): a.status for a in attendances}
    
    month_calendar = []
    for week in month_days_raw:
        week_days = []
        for d in week:
            d_str = d.strftime('%Y-%m-%d')
            is_current_month = (d.month == month)
            status = att_by_date.get(d_str, 'none' if is_current_month else 'other')
            week_days.append({
                'day': d.day,
                'date_str': d_str,
                'is_current_month': is_current_month,
                'status': status,
                'is_today': (d == datetime.date.today())
            })
        month_calendar.append(week_days)

    month_name = datetime.date(year, month, 1).strftime('%B %Y')

    search_date = request.GET.get('search_date', '')
    filtered_logs = attendances
    if search_date:
        filtered_logs = [a for a in attendances if search_date in a.date.strftime('%Y-%m-%d')]

    return render(request, 'student/attendance.html', {
        'admission': admission,
        'attendances': filtered_logs,
        'attendance_percentage': calc_percent,
        'present_count': present_count,
        'absent_count': absent_count,
        'half_day_count': half_day_count,
        'total_days': total_days,
        'month_calendar': month_calendar,
        'month_name': month_name,
        'year': year,
        'month': month,
        'search_date': search_date,
    })


@login_required
def student_news(request):
    admission = Admission.objects.filter(application__student=request.user, status='active').select_related('assigned_class', 'application__course', 'application__institute').first()
    notices = NoticeBoard.objects.filter(is_active=True).order_by('-created_at')
    return render(request, 'student/news.html', {
        'admission': admission,
        'notices': notices
    })


@login_required
def student_results(request):
    admission = Admission.objects.filter(application__student=request.user, status='active').select_related('assigned_class', 'application__course').first()
    results = AcademicResult.objects.filter(admission=admission).select_related('subject', 'period') if admission else []
    
    results_by_period = {}
    for res in results:
        period_name = res.period.name
        if period_name not in results_by_period:
            results_by_period[period_name] = []
        results_by_period[period_name].append(res)

    return render(request, 'student/results.html', {
        'admission': admission,
        'results_by_period': results_by_period
    })


@login_required
def student_timetable(request):
    admission = Admission.objects.filter(application__student=request.user, status='active').select_related('assigned_class').first()
    timetable = getattr(admission.assigned_class, 'timetable', None) if admission and admission.assigned_class else None
    return render(request, 'student/timetable.html', {
        'admission': admission,
        'timetable': timetable
    })


@login_required
def student_fees(request):
    admission = Admission.objects.filter(application__student=request.user).select_related('assigned_class', 'application__course').first()
    
    from academics.models import StudentFeePayment, FeeHead
    payments = list(StudentFeePayment.objects.filter(admission=admission, is_cancelled=False).select_related('fee_head__fee_type').order_by('-payment_date')) if admission else []
    
    total_paid = float(sum(p.amount_paid for p in payments)) if payments else 0.0
    fee_heads_raw = list(FeeHead.objects.filter(fee_structure__course=admission.application.course, is_active=True).select_related('fee_type')) if (admission and admission.application and admission.application.course) else []
    
    today = datetime.date.today()
    fee_heads_detail = []
    total_fee_tagged = 0.0
    next_due_date = None

    for fh in fee_heads_raw:
        paid_for_head = float(sum(p.amount_paid for p in payments if p.fee_head_id == fh.id)) if payments else 0.0
        due_for_head = max(0.0, float(fh.amount) - paid_for_head)
        total_fee_tagged += float(fh.amount)
        
        is_overdue = False
        if due_for_head > 0 and fh.due_date and today > fh.due_date:
            is_overdue = True
            
        if due_for_head > 0 and fh.due_date:
            if next_due_date is None or fh.due_date < next_due_date:
                next_due_date = fh.due_date

        fee_heads_detail.append({
            'head': fh,
            'amount': float(fh.amount),
            'paid_amount': paid_for_head,
            'due_amount': due_for_head,
            'due_date': fh.due_date,
            'is_overdue': is_overdue,
            'is_fully_paid': due_for_head <= 0
        })

    balance_due = max(0.0, total_fee_tagged - total_paid)

    return render(request, 'student/fees.html', {
        'admission': admission,
        'payments': payments,
        'total_paid': total_paid,
        'total_fee_tagged': total_fee_tagged,
        'balance_due': balance_due,
        'fee_heads': fee_heads_raw,
        'fee_heads_detail': fee_heads_detail,
        'next_due_date': next_due_date
    })


@login_required
def student_settings(request):
    admission = Admission.objects.filter(application__student=request.user, status='active').select_related('assigned_class', 'application__course', 'application__institute').first()
    return render(request, 'student/settings.html', {
        'admission': admission
    })



@login_required
def student_profile(request):
    admission = Admission.objects.filter(
        application__student=request.user
    ).select_related('assigned_class', 'application__course', 'application__institute').first()

    app = Application.objects.filter(student=request.user).first()

    if not admission and not app:
        messages.error(request, "Academic Profile is only available after Application or Enrolment.")
        return redirect('student_dashboard')

    from academics.models import StudentAttendance, StudentFeePayment, FeeHead, NoticeBoard, AcademicResult, StudentDocument
    from applications.models import ApplicationFieldValue

    # Photo extraction logic: Check user.profile_photo first, then application form photo
    student_photo_url = None
    if getattr(request.user, 'profile_photo', None):
        student_photo_url = request.user.profile_photo.url
    elif app:
        photo_fv = ApplicationFieldValue.objects.filter(
            application=app
        ).filter(
            Q(field__is_photo=True) | Q(field__label__icontains='photo') | Q(field__label__icontains='passport')
        ).first()
        if photo_fv and photo_fv.value and photo_fv.value != '-':
            val = str(photo_fv.value).strip()
            if val.startswith('/media/'):
                student_photo_url = val
            elif val.startswith('media/'):
                student_photo_url = '/' + val
            elif val.startswith('http://') or val.startswith('https://'):
                student_photo_url = val
            else:
                student_photo_url = f"/media/{val}"

    # Attendance metrics
    attendances = list(StudentAttendance.objects.filter(admission=admission).order_by('-date')) if admission else []
    total_days = len(attendances)
    present_count = sum(1 for a in attendances if a.status == 'present')
    absent_count = sum(1 for a in attendances if a.status == 'absent')
    half_day_count = sum(1 for a in attendances if a.status == 'half_day')
    attendance_pct = round(((present_count + 0.5 * half_day_count) / total_days * 100), 1) if total_days > 0 else 0

    # Fee metrics with itemized dues and due dates
    payments = list(StudentFeePayment.objects.filter(admission=admission, is_cancelled=False).select_related('fee_head__fee_type').order_by('-payment_date')) if admission else []
    total_paid = float(sum(p.amount_paid for p in payments)) if payments else 0.0
    fee_heads_raw = list(FeeHead.objects.filter(fee_structure__course=admission.application.course, is_active=True).select_related('fee_type')) if (admission and admission.application and admission.application.course) else []
    
    today = datetime.date.today()
    fee_heads_detail = []
    total_fee_tagged = 0.0
    next_due_date = None

    for fh in fee_heads_raw:
        paid_for_head = float(sum(p.amount_paid for p in payments if p.fee_head_id == fh.id)) if payments else 0.0
        due_for_head = max(0.0, float(fh.amount) - paid_for_head)
        total_fee_tagged += float(fh.amount)
        
        is_overdue = False
        if due_for_head > 0 and fh.due_date and today > fh.due_date:
            is_overdue = True
            
        if due_for_head > 0 and fh.due_date:
            if next_due_date is None or fh.due_date < next_due_date:
                next_due_date = fh.due_date

        fee_heads_detail.append({
            'head': fh,
            'amount': float(fh.amount),
            'paid_amount': paid_for_head,
            'due_amount': due_for_head,
            'due_date': fh.due_date,
            'is_overdue': is_overdue,
            'is_fully_paid': due_for_head <= 0
        })

    balance_due = max(0.0, total_fee_tagged - total_paid)

    # Notices
    notices = list(NoticeBoard.objects.filter(is_active=True).order_by('-created_at')[:10])

    # Timetable
    timetable = getattr(admission.assigned_class, 'timetable', None) if (admission and admission.assigned_class) else None

    # Results
    results = list(AcademicResult.objects.filter(admission=admission).select_related('subject', 'period')) if admission else []
    results_by_period = {}
    for res in results:
        period_name = res.period.name
        if period_name not in results_by_period:
            results_by_period[period_name] = []
        results_by_period[period_name].append(res)

    # Uploaded Documents (Only show student-uploaded/public documents, hide teacher-uploaded documents)
    uploaded_docs = list(StudentDocument.objects.filter(admission=admission, is_teacher_uploaded=False)) if admission else []

    return render(request, 'student/profile.html', {
        'admission': admission,
        'application': app,
        'student_photo_url': student_photo_url,
        'attendance_percentage': attendance_pct,
        'total_days': total_days,
        'present_count': present_count,
        'absent_count': absent_count,
        'half_day_count': half_day_count,
        'attendances': attendances[:15],
        'fee_heads': fee_heads_raw,
        'fee_heads_detail': fee_heads_detail,
        'next_due_date': next_due_date,
        'total_fee_tagged': total_fee_tagged,
        'total_paid': total_paid,
        'balance_due': balance_due,
        'payments': payments,
        'notices': notices,
        'timetable': timetable,
        'results_by_period': results_by_period,
        'uploaded_docs': uploaded_docs
    })


@login_required
def upload_student_photo(request):
    if request.method == 'POST' and request.FILES.get('photo'):
        photo_file = request.FILES['photo']
        request.user.profile_photo = photo_file
        request.user.save()
        messages.success(request, "Profile photo updated successfully!")
    else:
        messages.error(request, "Please select a valid image file.")
    return redirect(request.META.get('HTTP_REFERER', 'student_profile'))


@login_required
def settle_student_fee(request):
    if request.method == 'POST':
        head_id = request.POST.get('head_id')
        amount_paid = request.POST.get('amount')
        payment_mode = request.POST.get('payment_mode', 'online')
        
        admission = Admission.objects.filter(application__student=request.user).first()
        if not admission:
            messages.error(request, "Enrolment record not found.")
            return redirect('student_profile')
            
        from academics.models import FeeHead, StudentFeePayment
        from institutes.views import generate_receipt_number
        
        try:
            amt_val = float(amount_paid) if amount_paid else 0.0
            if amt_val <= 0:
                messages.error(request, "Invalid payment amount.")
                return redirect('student_profile')
                
            fee_head = None
            if head_id:
                fee_head = FeeHead.objects.filter(id=head_id).first()
            if not fee_head:
                fee_head = FeeHead.objects.filter(fee_structure__course=admission.application.course, is_active=True).first()
                
            rcpt_no = generate_receipt_number()
            StudentFeePayment.objects.create(
                admission=admission,
                fee_head=fee_head,
                amount_paid=amt_val,
                payment_mode=payment_mode,
                reference_no=f"STU-{request.user.id}-{int(datetime.datetime.now().timestamp())}",
                receipt_number=rcpt_no,
                remarks="Payment settled via Student Portal",
                payment_date=datetime.date.today()
            )
            messages.success(request, f"Payment of ₹{amt_val:.2f} settled successfully! Receipt #{rcpt_no} generated.")
        except Exception as e:
            messages.error(request, f"Failed to settle payment: {str(e)}")
            
    return redirect('student_profile')


@login_required
def my_applications(request):
    apps = Application.objects.filter(student=request.user).select_related('course')
    return render(request, 'student/my_applications.html', {'apps': apps})

@login_required
def apply_course(request):
    # Filter institutes that have courses with active application forms
    institutes = Institute.objects.filter(courses__form__is_active=True).distinct()
    
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
        # 1. Try to find the selected exam ID from the form submission
        selected_exam_id = None
        for key, val in request.POST.items():
            if key.startswith("field_"):
                # Check if this field is the one that triggers handleExamChange
                f_id = key.replace("field_", "")
                f_obj = FormField.objects.filter(id=f_id).first()
                if f_obj and ("exam" in f_obj.label.lower() or "qualifying" in f_obj.label.lower()) and val:
                    selected_exam_id = val
                    break

        subjects_to_save = []
        for key in request.POST:
            if key.startswith("subject_"):
                # Handle underscores that might have been converted from spaces
                subject_name = key.replace("subject_", "").replace("_", " ")
                marks_str = request.POST.get(key)
                
                if marks_str:
                    try:
                        marks_val = float(marks_str)
                        
                        # Robust Exam & Subject Lookup
                        exam_obj = None
                        if selected_exam_id:
                            if str(selected_exam_id).isdigit():
                                exam_obj = QualifyingExam.objects.filter(id=selected_exam_id).first()
                            if not exam_obj:
                                exam_obj = QualifyingExam.objects.filter(name__iexact=selected_exam_id).first()
                        
                        subj_obj = None
                        if exam_obj:
                            subj_obj = ExamSubject.objects.filter(name__iexact=subject_name, exam=exam_obj).first()
                        else:
                            subj_obj = ExamSubject.objects.filter(name__iexact=subject_name).first()
                        
                        max_val = subj_obj.max_marks if subj_obj else 100
                        pass_val = subj_obj.pass_mark if subj_obj else 0
                        
                        if marks_val > max_val or marks_val < pass_val:
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
        form_obj = ApplicationForm.objects.get(course_id=course_id)
        fields = form_obj.fields.all()

        for field in fields:
            key = f'field_{field.id}'
            
            # REQUIREMENT: Required field validation
            if field.required:
                if field.field_type == 'file':
                    if key not in request.FILES:
                        messages.error(request, f"The field '{field.label}' is required.")
                        application.delete() # Rollback application creation
                        return redirect('/apply/')
                else:
                    if not request.POST.get(key):
                        messages.error(request, f"The field '{field.label}' is required.")
                        application.delete() # Rollback
                        return redirect('/apply/')

            if field.field_type == 'file':
                file_obj = request.FILES.get(key)
                if file_obj:
                    # REQUIREMENT: 1 MB file size limit
                    if file_obj.size > 1 * 1024 * 1024:
                        messages.error(request, f"File '{file_obj.name}' exceeds the 1 MB limit.")
                        application.delete()
                        return redirect('/apply/')

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
        # Link subjects to the 'Qualifying Examination' field or similar
        # Use current form to avoid cross-form linking
        qe_field = FormField.objects.filter(form=form_obj, section__name__icontains="Qualifi").first()
        if not qe_field:
            qe_field = FormField.objects.filter(form=form_obj, label__icontains="Qualifi").first()
        if not qe_field:
            # Fallback to any field in a section with 'mark' in it
            qe_field = FormField.objects.filter(form=form_obj, section__name__icontains="mark").first()

        for sub in subjects_to_save:
            ApplicationFieldValue.objects.create(
                application=application,
                field=qe_field,
                field_label=qe_field.label if qe_field else "Subject Mark",
                value=f"{sub['name']}:{sub['marks']}:{sub['max']}"
            )

        # =========================
        # HANDLE FEE CATEGORY (NEW)
        # =========================
        fee_type_id = request.POST.get('selected_fee_type')
        fee_amount = form_obj.registration_fee # Default
        
        if fee_type_id:
            try:
                selected_type = ApplicationFeeType.objects.get(id=fee_type_id, form=form_obj)
                application.selected_fee_type = selected_type
                application.save()
                fee_amount = selected_type.amount
            except ApplicationFeeType.DoesNotExist:
                pass

        # =========================
        # PAYMENT INITIATION OR DIRECT SUBMISSION
        # =========================
        payment = Payment.objects.create(
            application=application,
            amount=fee_amount,
            gateway_config=form_obj.payment_config
        )

        if fee_amount <= 0:
            # DIRECT SUBMISSION (NO FEE)
            payment.status = 'success'
            payment.save()
            application.status = 'submitted'
            application.save()
            messages.success(request, "Application submitted successfully!")
            return redirect('/my-applications/')

        return redirect(f'/payment/{application.id}/')

    return render(request, 'student/form.html', {
        'institutes': institutes,
        'academic_years': academic_years,
        'active_year': active_year
    })
@login_required
def payment_page(request, app_id):
    print(f"\n[DEBUG] Entering payment_page for app_id: {app_id}, method: {request.method}", flush=True)
    from .payment_handlers import CCAvenueHandler, PhiCommerceHandler
    
    application = get_object_or_404(Application, id=app_id, student=request.user)
    try:
        payment = Payment.objects.get(application=application)
    except Payment.DoesNotExist:
        messages.error(request, "Payment information not found for this application.")
        return redirect('/my-applications/')
    
    config = payment.gateway_config
    
    if request.method == 'POST' and config:
        print(f"\n[DEBUG] Pay Now Clicked. Gateway: {config.gateway_type}", flush=True)
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
            
            # Save merchantTxnNo for tracking
            payment.merchant_txn_no = data.get('merchant_txn_no')
            payment.save()
            
            print(f"\n[DEBUG] PhiCommerce Redirecting to: {data['action_url']}", flush=True)
            return redirect(data['action_url'])

    return render(request, 'student/payment.html', {
        'application': application,
        'payment': payment,
        'config': config
    })


@csrf_exempt
def ccavenue_callback(request):
    from .payment_handlers import CCAvenueHandler, cc_decrypt
    from .models import PaymentConfig, Payment
    
    configs = PaymentConfig.objects.filter(gateway_type='ccavenue', is_active=True)
    if not configs.exists():
        messages.error(request, "Payment configuration not found.")
        return redirect('/my-applications/')
        
    data = request.POST if request.method == 'POST' else request.GET
    enc_resp = data.get('encResp') or data.get('encresp')
    
    if not enc_resp:
        messages.error(request, "No response data received from payment gateway.")
        return redirect('/my-applications/')
        
    enc_resp = enc_resp.strip()
    
    decrypted_data = None
    successful_config = None
    
    # Try decrypting with each active CCAvenue config's working key
    for config in configs:
        if not config.working_key:
            continue
        try:
            dec_resp = cc_decrypt(enc_resp, config.working_key)
            resp_dict = {}
            for item in dec_resp.split("&"):
                if "=" in item:
                    parts = item.split("=", 1)
                    resp_dict[parts[0]] = parts[1]
            
            if resp_dict.get('order_id'):
                decrypted_data = resp_dict
                successful_config = config
                break
        except Exception:
            continue
            
    if not decrypted_data or not successful_config:
        messages.error(request, "Payment verification failed (decryption error).")
        return redirect('/my-applications/')
        
    handler = CCAvenueHandler(successful_config)
    result = handler.verify_payment(data)
    
    # Tracking
    raw_response = result.get('raw') or decrypted_data
    order_id = raw_response.get('order_id')
    
    if order_id:
        try:
            payment = Payment.objects.get(id=order_id)
            payment.gateway_response = raw_response
            payment.gateway_transaction_id = result.get('txn_id')
            
            # Map and normalize payment_mode safely to avoid DB field length constraints (max 10 chars)
            mode_raw = str(result.get('payment_mode') or '').strip().upper()
            std_mode = None
            if 'CARD' in mode_raw:
                std_mode = 'CARD'
            elif 'UPI' in mode_raw or 'VPA' in mode_raw:
                std_mode = 'UPI'
            elif 'BANK' in mode_raw or 'NB' in mode_raw or 'NET' in mode_raw:
                std_mode = 'NB'
            else:
                std_mode = mode_raw[:10] if mode_raw else None
            payment.payment_mode = std_mode
            
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
        except (Payment.DoesNotExist, ValueError, TypeError) as e:
            messages.error(request, f"Payment record not found for Order ID: {order_id}")
            
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
    
    print("\n====== PHICOMMERCE CALLBACK RECEIVED ======", flush=True)
    print(data, flush=True)
    
    if result['status'] == 'success':
        merchant_txn_no = result.get('merchant_txn_no', '')
        print(f"Searching for payment with merchant_txn_no: {merchant_txn_no}", flush=True)
        try:
            payment = Payment.objects.get(merchant_txn_no=merchant_txn_no)
            
            # Update only if not already processed by webhook
            if payment.status == 'pending':
                payment.gateway_response = result.get('raw')
                payment.gateway_transaction_id = result.get('txn_id') # Update with bank ref
                payment.payment_mode = result.get('payment_mode')
                payment.status = 'success'
                payment.save()
                
                application = payment.application
                application.status = 'submitted'
                application.save()
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
    
    print("\n====== PHICOMMERCE WEBHOOK RECEIVED ======", flush=True)
    print(data, flush=True)
    
    if result['status'] == 'success':
        merchant_txn_no = result.get('merchant_txn_no', '')
        try:
            payment = Payment.objects.get(merchant_txn_no=merchant_txn_no)
            
            # Background update
            if payment.status == 'pending':
                payment.gateway_response = result.get('raw')
                payment.payment_mode = result.get('payment_mode')
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
    if not institute_id:
        return JsonResponse([], safe=False)

    # Fetch years that have active application forms in this institute
    year_ids = ApplicationForm.objects.filter(
        course__institute_id=institute_id, 
        is_active=True
    ).values_list('academic_year_id', flat=True).distinct()
    
    years = AcademicYear.objects.filter(id__in=year_ids, is_active=True).values('id', 'name')
    return JsonResponse(list(years), safe=False)


def load_courses(request):
    institute_id = request.GET.get('institute_id')
    year_id = request.GET.get('academic_year_id')
    
    if not institute_id:
        return JsonResponse([], safe=False)

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
    if not course_id:
        return JsonResponse([], safe=False)

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
            'placeholder': field.placeholder,
            'required': field.required,
            'is_photo': field.is_photo,
            'is_signature': field.is_signature,
            'options': [
                {'value': opt.value, 'text': opt.display_text}
                for opt in field.options.all()
            ],
        })

    fee_types = [
        {'id': ft.id, 'name': ft.name, 'amount': str(ft.amount)}
        for ft in form.fee_types.filter(is_active=True)
    ]

    return JsonResponse({'fields': data, 'fee_types': fee_types}, safe=False)


@login_required
def upload_document(request):
    if request.method == 'POST':
        admission = Admission.objects.filter(application__student=request.user, status='active').first()
        if admission:
            title = request.POST.get('title')
            file = request.FILES.get('file')
            if title and file:
                StudentDocument.objects.create(
                    admission=admission,
                    title=title,
                    file=file
                )
                messages.success(request, "Document uploaded to vault.")
            else:
                messages.error(request, "Please provide a title and file.")
        else:
            messages.error(request, "Admission record not found.")
    return redirect('student_profile')


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
    field_values = list(application.field_values.select_related('field', 'field__section').all())

    # Identify photo and signature
    student_photo = None
    student_signature = None

    # We also need to separate normal fields from subject marks
    normal_fields = []
    subject_marks = []
    total_obtained = 0
    total_max = 0

    # 1. Identify Qualifying Exam and Subjects Configuration
    from academics.models import QualifyingExam, ExamSubject
    exam_obj = None
    
    # Step A: Find the examination name from the form values
    exam_name_from_form = None
    for fv in field_values:
        label = (fv.field.label if fv.field else fv.field_label or "").lower()
        if ("exam" in label or "qualifying" in label) and "marks" not in label:
            val = str(fv.value).strip()
            # If it's a choice field, get the display text first
            if fv.field and fv.field.field_type in ['select', 'radio']:
                from academics.models import FieldOption
                opt = FieldOption.objects.filter(field=fv.field, value=val).first()
                if opt:
                    exam_name_from_form = opt.display_text
            
            # Fallback to the raw value if no option found
            if not exam_name_from_form:
                exam_name_from_form = val
            break

    # Step B: Resolve the QualifyingExam object based on the name we found
    subjects_config = {}
    if exam_name_from_form:
        # Try finding by name (this is more reliable than ID which might mismatch with FieldOptions)
        exam_obj = QualifyingExam.objects.filter(name__iexact=exam_name_from_form).first()
        if exam_obj:
            for s in ExamSubject.objects.filter(exam=exam_obj):
                subjects_config[s.name.lower().strip()] = s.max_marks
        
        # Fallback to ID if name lookup fails and it's numeric
        if not exam_obj and exam_name_from_form.isdigit():
            exam_obj = QualifyingExam.objects.filter(id=exam_name_from_form).first()

    subjects_config = {}
    if exam_obj:
        for s in ExamSubject.objects.filter(exam=exam_obj):
            subjects_config[s.name.lower().strip()] = s.max_marks

    # 2. Process ALL field values to extract marks and media (including orphans/mislinked)
    processed_fv_ids = set()
    for fv in field_values:
        # Check if the field belongs to a qualification/marks section or label
        label_lower = (fv.field.label if fv.field else fv.field_label or "").lower()
        val_str = str(fv.value or "").strip()
        section_lower = (fv.field.section.name if fv.field and fv.field.section else fv.field_label or "").lower()
        is_qual_field = any(x in label_lower or x in section_lower for x in ["mark", "subject", "qualify", "exam"])

        is_mark_format = ":" in val_str and len(val_str.split(":")) >= 2 and is_qual_field
        is_media_field = any(x in label_lower for x in ["photo", "signature", "sign"])
        
        # Check if the first part looks like a subject name (not a URL or path)
        if is_mark_format and not is_media_field:
            try:
                parts = val_str.split(":")
                name = parts[0].strip()
                marks_str = parts[1].strip()
                
                # Verify marks part is numeric
                try:
                    marks_val = float(marks_str)
                    
                    # Dynamic Max Marks Lookup
                    max_val = 100
                    if len(parts) >= 3:
                        try:
                            max_val = float(parts[2])
                        except:
                            max_val = subjects_config.get(name.lower().strip(), 100)
                    else:
                        max_val = subjects_config.get(name.lower().strip(), 100)
                    
                    if not max_val or max_val == 0:
                        max_val = 100
                    
                    total_obtained += marks_val
                    total_max += max_val
                    subject_marks.append({'name': name, 'marks': marks_val, 'max': max_val})
                    processed_fv_ids.add(fv.id)
                except ValueError:
                    # Not a numeric mark, skip identifying as subject mark
                    pass
            except (IndexError):
                pass
        
        # Identify photo and signature
        elif (fv.field and fv.field.is_photo) or "photo" in label_lower or "passport" in label_lower:
            if not student_photo and fv.value != '-':
                student_photo = fv.value
            processed_fv_ids.add(fv.id)
        elif (fv.field and fv.field.is_signature) or "signature" in label_lower or "sign" in label_lower:
            if not student_signature and fv.value != '-':
                student_signature = fv.value
            processed_fv_ids.add(fv.id)

    # 3. Fetch ALL fields defined for this form to include non-filled ones
    from academics.models import FormField
    all_form_fields = FormField.objects.filter(form=application.course.form).select_related('section').order_by('section__order', 'order')
    
    # Map existing values to fields for easy lookup
    field_to_values = {}
    for fv in field_values:
        if fv.field_id not in field_to_values:
            field_to_values[fv.field_id] = []
        field_to_values[fv.field_id].append(fv)

    # Process all fields for structured display
    for field in all_form_fields:
        values = field_to_values.get(field.id, [])
        
        if not values:
            # Create a mock fv for empty fields
            mock_fv = type('MockFV', (), {
                'field': field,
                'field_label': field.label,
                'value': '-',
                'display_value': '-',
                'id': None
            })
            values = [mock_fv]

        for fv in values:
            if fv.id and fv.id in processed_fv_ids:
                continue

            label_lower = (fv.field.label if fv.field else fv.field_label or "").lower()
            label = fv.field.label if fv.field else fv.field_label
            
            val = str(fv.value).strip()
            if not hasattr(fv, 'display_value'):
                fv.display_value = val
            
            # Resolve Display Text for Select/Dropdown fields
            if fv.field and fv.field.field_type in ['select', 'radio'] and val != '-':
                from academics.models import FieldOption
                opt = FieldOption.objects.filter(field=fv.field, value=val).first()
                if opt:
                    fv.display_value = opt.display_text

            # If this is the exam field, ensure it shows the correctly resolved name
            if ("exam" in label_lower or "qualifying" in label_lower) and "marks" not in label_lower:
                if exam_obj:
                    fv.display_value = exam_obj.name
            
            # Robust ID-to-Name resolution for Full Name fallback
            if ("name" in label_lower or "candidate" in label_lower) and (not val or ":" in val or val == "None" or not val.strip() or val == "-"):
                if val == "-":
                    fv.display_value = application.student.first_name if application.student.first_name else application.student.username
                else:
                    fv.display_value = val
            
            normal_fields.append(fv)

    percentage = (total_obtained / total_max * 100) if total_max > 0 else 0

    from .models import Payment
    payment = Payment.objects.filter(application=application).first()

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
        'payment': payment,
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
    if not exam_id:
        return JsonResponse([], safe=False)

    subjects = ExamSubject.objects.filter(exam_id=exam_id)

    data = [
        {'name': sub.name, 'max_marks': sub.max_marks, 'pass_mark': sub.pass_mark}
        for sub in subjects
    ]

    return JsonResponse(data, safe=False)