from django.urls import path

from .views import FindingImageView, FindingPreviewView

app_name = "faces"

urlpatterns = [
    path(
        "finding-image/<path:filename>/",
        FindingImageView.as_view(),
        name="finding-image",
    ),
    path(
        "finding-preview/<int:pk>/",
        FindingPreviewView.as_view(),
        name="finding-preview",
    ),
]
