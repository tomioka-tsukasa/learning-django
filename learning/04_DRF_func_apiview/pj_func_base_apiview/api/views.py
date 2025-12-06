from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from datetime import datetime, timezone
import pytz
from pytz.exceptions import UnknownTimeZoneError
from rest_framework import status

# Create your views here.

def index(request):
  return HttpResponse('<h1>Hello</h1>')
  # return JsonResponse({'page': 'home'})

@api_view(['GET', 'POST', 'PUT', 'DELETE'])
def country_datetime(request):
  """
  指定されたタイムゾーンの現在日時を返すAPIエンドポイント

  Args:
    request: DRFのリクエストオブジェクト
      - GET/POST: timezone パラメータでタイムゾーンを指定可能
      - PUT: PUTメソッドのテスト用
      - DELETE: DELETEメソッドのテスト用

  Returns:
    Response: JSON形式のレスポンス
      - timezone指定時: 指定されたタイムゾーンの現在日時
      - timezone未指定時: サーバーのローカル時刻

  Raises:
    400 Bad Request: 存在しないタイムゾーンが指定された場合

  Examples:
    POST /api/country_datetime
    {
      "timezone": "Asia/Tokyo"
    }

    Response:
    {
      "Datetime POST: Asia/Tokyo": "2025-11-30 12:34:56+09:00"
    }
  """
  # POST
  if request.method == 'POST':
    print(request.data)
    requested_timezone = request.data.get('timezone')
    if requested_timezone:
      try:
        tz = pytz.timezone(requested_timezone) # requestで指定したタイムゾーン
      except UnknownTimeZoneError as e:
        return Response({"Error POST": "Timezone not exists"}, status=status.HTTP_400_BAD_REQUEST)

      utc_timezone = datetime.now(timezone.utc) # utc時刻
      return Response({ # utc -> timezone
        f"Datetime POST: {requested_timezone}": utc_timezone.astimezone(tz)
      })
  # PUT

  elif request.method == 'PUT':
    print('PUTが呼ばれました')

  # DELETE
  elif request.method == 'DELETE':
    print('DELETEが呼ばれました')

  # GET
  elif request.method == 'GET':
    requested_timezone = request.query_params.get('timezone')
    if requested_timezone:
      try:
        tz = pytz.timezone(requested_timezone) # requestで指定したタイムゾーン
      except UnknownTimeZoneError as e:
        return Response({"Error GET": "Timezone not exists"}, status=status.HTTP_400_BAD_REQUEST)

      utc_timezone = datetime.now(timezone.utc) # utc時刻
      return Response({ # utc -> timezone
        f"Datetime GET: {requested_timezone}": utc_timezone.astimezone(tz)
      })

  return Response({'Datetime': datetime.now()})
