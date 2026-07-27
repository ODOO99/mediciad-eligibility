from django.urls import path
from . import views

app_name = 'imports'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_import, name='upload'),
    path('progress/<int:batch_id>/sse/', views.progress_sse, name='progress_sse'),
    path('progress/<int:batch_id>/poll/', views.progress_poll, name='progress_poll'),
    path('results/<int:batch_id>/', views.results, name='results'),
    path('cancel/<int:batch_id>/', views.cancel_batch, name='cancel'),
    path('retry/<int:batch_id>/', views.retry_failed_rows, name='retry'),
    path('sample/', views.download_sample_csv, name='sample_csv'),
    path('settings/', views.app_settings, name='settings'),
    path('settings/wipe/', views.wipe_all_data, name='wipe_all_data'),
]
