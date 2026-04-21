from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render

# ✅ FOR MEDIA FILES (UPLOADS)
from django.conf import settings
from django.conf.urls.static import static

# ✅ OPTIONAL REDIRECTS
from django.shortcuts import redirect
from applications.views import load_exam_subjects

def home(request):
    return render(request, 'home.html')


urlpatterns = [
    path('admin/', admin.site.urls),

    # ✅ ACCOUNTS (LOGIN / REGISTER)
    path('accounts/', include('accounts.urls')),

    # ✅ STUDENT APPLICATIONS
    path('', include('applications.urls')),

    # ✅ INSTITUTE PANEL
    path('institute/', include('institutes.urls')),

    # ✅ ACADEMICS (FORM BUILDER)
    path('academics/', include('academics.urls')),
    path('load_exam_subjects/', load_exam_subjects),
    path('', home, name='home'),
]


# ✅ OPTIONAL: SHORT URL REDIRECTS
urlpatterns += [
    path('login/', lambda request: redirect('/accounts/login/')),
    path('logout/', lambda request: redirect('/accounts/logout/')),
    path('register/', lambda request: redirect('/accounts/register/')),
]


# ✅ MEDIA FILE SERVING
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)