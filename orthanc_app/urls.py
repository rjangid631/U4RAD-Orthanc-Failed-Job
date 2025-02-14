from django.urls import path
from .views import fetch_failed_jobs, retry_failed_jobs, home
#from . import views
urlpatterns = [
    path('', home, name='home'),
    path('fetch-failed-jobs/', fetch_failed_jobs, name='fetch_failed_jobs'),
    path('retry-failed-jobs/', retry_failed_jobs, name='retry_failed_jobs'),
]