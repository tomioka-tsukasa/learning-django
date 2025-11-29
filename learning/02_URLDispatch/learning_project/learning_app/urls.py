from django.urls import path
from . import views

app_name = 'learning_app'

urlpatterns = [
  path('user/<str:user_name>', views.user_page, name='user_page'),
]
