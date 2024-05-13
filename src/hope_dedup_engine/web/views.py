from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse


def healthcheck(request: HttpRequest) -> HttpResponse:
    return HttpResponse("OK")


def index(request: "HttpRequest") -> TemplateResponse:
    return TemplateResponse(request, "home.html", {})
