import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Course, ApplicationForm, FormField, AcademicEvent
from .forms import CourseForm
from institutes.models import Institute, AcademicYear
from institutes.views import get_current_institute


# ✅ CREATE COURSE
@login_required
def create_course(request):
    messages.info(request, "Program creation is restricted. Please contact your IT Administrator to establish or configure new programs.")
    return redirect('course_list')


# ✅ CREATE FORM BUILDER
def create_form(request, course_id):
    course = Course.objects.get(id=course_id)

    form, created = ApplicationForm.objects.get_or_create(course=course)

    if request.method == 'POST':
     label = request.POST.get('label')
     field_type = request.POST.get('field_type')
     section_id = request.POST.get('section')
     placeholder = request.POST.get('placeholder')
     order = request.POST.get('order') or 0
     required = True if request.POST.get('required') == 'on' else False

    if label and section_id:
        FormField.objects.create(
            form=form,
            section_id=section_id,
            label=label,
            field_type=field_type,
            placeholder=placeholder,
            order=order,
            required=required
        )

    fields = form.formfield_set.all()

    return render(request, 'academics/create_form.html', {
        'course': course,
        'fields': fields
    })


# ✅ COURSE LIST
@login_required
def course_list(request):
    institute = get_current_institute(request)
    courses = Course.objects.filter(institute=institute)

    return render(request, 'academics/course_list.html', {
        'courses': courses
    })


# ✅ ACADEMIC CALENDAR & UPCOMING EVENTS
@login_required
def manage_academic_events(request):
    institute = get_current_institute(request)
    if not institute and (request.user.is_staff or request.user.is_superuser):
        institute = Institute.objects.first()

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        event_type = request.POST.get('event_type', 'event')
        start_date_str = request.POST.get('start_date', '').strip()
        end_date_str = request.POST.get('end_date', '').strip()
        description = request.POST.get('description', '').strip()
        is_holiday = request.POST.get('is_holiday') == 'on' or event_type == 'holiday'

        if not title:
            messages.error(request, "Event title is required.")
        elif not start_date_str:
            messages.error(request, "Start date is required.")
        else:
            try:
                start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
                if end_date and end_date < start_date:
                    messages.error(request, "End date cannot be earlier than start date.")
                else:
                    active_year = AcademicYear.objects.filter(institute=institute, is_active=True).first()
                    AcademicEvent.objects.create(
                        institute=institute,
                        academic_year=active_year,
                        title=title,
                        event_type=event_type,
                        start_date=start_date,
                        end_date=end_date,
                        description=description,
                        is_holiday=is_holiday,
                        created_by=request.user
                    )
                    messages.success(request, f"Event '{title}' added to calendar successfully!")
                    return redirect('manage_academic_events')
            except Exception as e:
                messages.error(request, f"Error saving event: {str(e)}")

    events = AcademicEvent.objects.filter(institute=institute).order_by('start_date', 'id')
    today = datetime.date.today()
    upcoming_events = events.filter(start_date__gte=today).order_by('start_date')
    past_events = events.filter(start_date__lt=today).order_by('-start_date')
    holidays_count = events.filter(is_holiday=True).count()

    return render(request, 'academics/academic_events.html', {
        'events': events,
        'upcoming_events': upcoming_events,
        'past_events': past_events,
        'holidays_count': holidays_count,
        'total_events_count': events.count(),
        'today': today,
        'today_str': today.strftime('%Y-%m-%d'),
    })


@login_required
def delete_academic_event(request, event_id):
    institute = get_current_institute(request)
    event = get_object_or_404(AcademicEvent, id=event_id, institute=institute)
    if request.method == 'POST':
        title = event.title
        event.delete()
        messages.success(request, f"Event '{title}' removed from calendar.")
    return redirect('manage_academic_events')