import mimetypes
from functools import wraps
from typing import Any
from azure.core.exceptions import ResourceNotFoundError
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django.urls import reverse

from hope_dedup_engine.apps.api.models import Finding, Encoding
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager
from hope_dedup_engine.apps.api.permissions import can_view_finding_details


def finding_details_required(view_func):
    """Allow access only to users with finding details permission."""

    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args: Any, **kwargs: Any):
        if not can_view_finding_details(request):
            raise Http404("Not found")
        return view_func(request, *args, **kwargs)

    return _wrapped


access_decorators = (staff_member_required, finding_details_required)


@method_decorator(access_decorators, name="dispatch")
class FindingImageView(View):
    """Serve image files from hope storage to the browser."""

    def setup(self, request: HttpRequest, *args, **kwargs) -> None:
        super().setup(request, *args, **kwargs)
        self.storage_manager = ImagesStorageManager()

    def get(self, request: HttpRequest, filename: str, *args, **kwargs) -> HttpResponse:
        try:
            file_obj = self.storage_manager.storage.open(filename, "rb")
        except (ResourceNotFoundError, FileNotFoundError) as exc:
            raise Http404("Image not found") from exc

        content_type, _ = mimetypes.guess_type(filename)
        return FileResponse(
            file_obj,
            content_type=content_type or "application/octet-stream",
            as_attachment=False,
            filename=filename,
        )


@method_decorator(access_decorators, name="dispatch")
class FindingPreviewView(TemplateView):
    """Render a simple page with both images for a single Finding."""

    template_name = "admin/api/finding_preview.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        finding = get_object_or_404(
            Finding.objects.select_related("first_encoding", "second_encoding"),
            pk=self.kwargs["pk"],
        )
        first, second = finding.first_encoding, finding.second_encoding
        context.update(
            finding=finding,
            status_label=Encoding.StatusCode(finding.status_code).label,
            first_image_url=self._image_url(first.filename),
            second_image_url=self._image_url(second.filename if second else None),
        )
        return context

    @staticmethod
    def _image_url(filename: str | None) -> str | None:
        if not filename:
            return None
        return reverse("finding-image", kwargs={"filename": filename})
