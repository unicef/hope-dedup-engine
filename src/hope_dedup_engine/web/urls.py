from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="home"),
    path("healthcheck", views.healthcheck, name="healthcheck"),
    path("healthcheck/", views.healthcheck, name="healthcheck"),
]
