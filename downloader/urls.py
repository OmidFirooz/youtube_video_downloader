from django.urls import path
from . import views

urlpatterns = [
    path('', views.download_video, name='download_video'),
    path('status/<str:task_id>/', views.download_status_view, name='download_status'),
    path('serve/<str:task_id>/', views.serve_file, name='serve_file'),
]