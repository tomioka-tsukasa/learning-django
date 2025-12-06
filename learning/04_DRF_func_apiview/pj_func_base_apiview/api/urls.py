from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('country_datetime/', views.country_datetime, name='country_datetime')
]
