import mimetypes
from typing import Any
from azure.core.exceptions import ResourceNotFoundError
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django.urls import reverse

from hope_dedup_engine.apps.api.models import Finding, Encoding
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager


@method_decorator(staff_member_required, name="dispatch")
class FindingDetailsPermissionMixin(PermissionRequiredMixin):
    permission_required = "api.view_finding_details"


class FindingImageView(FindingDetailsPermissionMixin, View):
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


class FindingPreviewView(FindingDetailsPermissionMixin, TemplateView):
    """Render a simple page with both images for a single Finding."""

    template_name = "admin/api/finding/details.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        finding = get_object_or_404(
            Finding.objects.select_related("first_encoding", "second_encoding"),
            pk=self.kwargs["pk"],
        )
        first, second = finding.first_encoding, finding.second_encoding
        context.update(
            page_title=f"Finding {finding.pk} details",
            title=f"Finding {finding.pk} details",
            opts=Finding._meta,
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
        return reverse("admin:api_finding_image", kwargs={"filename": filename})
