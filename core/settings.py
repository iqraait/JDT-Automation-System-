from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'secret-key'



DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
     'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'accounts',
    'institutes',
    'applications',
    'academics',
    
]

AUTH_USER_MODEL = 'accounts.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
            ],
        },
    },
]

JAZZMIN_SETTINGS = {
    #  Branding
    "site_title": "JDT College Admin",
    "site_header": "JDT Automation",
    "site_brand": "JDT Admin Node",
    "site_logo": None,  # Can add a path to a static logo if available
    "login_logo": None,
    "login_logo_dark": None,
    "site_icon": None,
    "welcome_sign": "Welcome to JDT Administrative Control",
    "copyright": "JDT Islam College Admissions",
    "search_model": ["accounts.User", "applications.Application"],
    "user_avatar": None,

    #  Navigation
    "topmenu_links": [
        {"name": "Home",  "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "View Web Portal", "url": "/", "new_window": True},
        {"name": "Support", "url": "https://iqraa.it", "new_window": True},
    ],
    "usermenu_links": [
        {"name": "Support", "url": "https://iqraa.it", "new_window": True},
        {"model": "accounts.user"},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": ["accounts", "institutes", "academics", "applications"],
    
    # 💎 Icons (Unique Sapphire Set)
    "icons": {
        "accounts": "fas fa-users-cog",
        "accounts.user": "fas fa-user-shield",
        "auth": "fas fa-users-cog",
        "auth.group": "fas fa-users",
        "institutes": "fas fa-university",
        "institutes.institute": "fas fa-school",
        "academics": "fas fa-book-reader",
        "academics.course": "fas fa-graduation-cap",
        "academics.section": "fas fa-layer-group",
        "academics.field": "fas fa-align-left",
        "academics.selectoption": "fas fa-list-ul",
        "applications": "fas fa-file-signature",
        "applications.application": "fas fa-user-edit",
        "applications.applicationfield": "fas fa-check-double",
    },
    
    # 💎 Display
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": True,
    "custom_css": "admin/custom_admin_style.css",
    "custom_js": None,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {"auth.user": "collapsible_list", "auth.group": "vertical_tabs"},
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

PHICOMMERCE_USE_UAT = True

# Email Configuration (Real Gmail)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'erp@jdticas.in'
EMAIL_HOST_PASSWORD = 'crfk wcys naik svzv'
DEFAULT_FROM_EMAIL = 'erp@jdticas.in'
