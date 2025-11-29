import requests

url = 'http://localhost:8000/api/country_datetime'
response = requests.get(url, params={"timezone": "US/Eastern"})

print(response.status_code)
print(response.text)
print(response.headers)
