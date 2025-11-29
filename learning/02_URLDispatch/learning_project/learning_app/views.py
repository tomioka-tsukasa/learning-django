from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.

def user_page(request, user_name):
  print(type(user_name), user_name)
  return HttpResponse(f'<h1>Hello {user_name}</h1>')
