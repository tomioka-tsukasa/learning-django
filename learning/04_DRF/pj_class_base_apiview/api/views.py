from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response

# Create your views here.

class ItemView(APIView):

  def get(self, request):
    return Response({"method": "get"})

  def post(self, request):
    return Response({"method": "post"})

  def put(self, request):
    return Response({"method": "put"})

  def delete(self, request):
    return Response({"method": "delete"})
