from django.urls import path
from . import views

app_name = 'eligibility'

urlpatterns = [
    path('history/', views.history, name='history'),
    path('response/<int:response_id>/', views.response_detail, name='response_detail'),
    path('response/<int:response_id>/raw/', views.raw_response, name='raw_response'),
]
