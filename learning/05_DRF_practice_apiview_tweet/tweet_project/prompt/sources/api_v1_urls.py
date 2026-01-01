from django.urls import include, path

urlpatterns = [
    path("user/", include("user.urls")),
    path("tweets/", include("tweets.urls")),
]
