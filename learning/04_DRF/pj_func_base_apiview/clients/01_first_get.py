import requests

url = 'http://localhost:8000/api/'
response = requests.get(url)

print(response.text)
print(response.headers)
