from django.shortcuts import render, redirect
from .models import Course, ApplicationForm, FormField
from .forms import CourseForm
from institutes.models import Institute


# ✅ CREATE COURSE
def create_course(request):
    institute = Institute.objects.get(user=request.user)

    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.institute = institute
            course.save()
            return redirect('institute_dashboard')
    else:
        form = CourseForm()

    return render(request, 'academics/create_course.html', {'form': form})


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
def course_list(request):
    institute = Institute.objects.get(user=request.user)
    courses = Course.objects.filter(institute=institute)

    return render(request, 'academics/course_list.html', {
        'courses': courses
    })