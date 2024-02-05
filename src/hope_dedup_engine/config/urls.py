from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path

root_patterns = [
    path(r"admin/", admin.site.urls),
    path(r"security/", include("unicef_security.urls", namespace="security")),
    path(r"social/", include("social_django.urls", namespace="social")),
]

api_patterns = [
    path(r"accounts/", include("django.contrib.auth.urls")),
    path(r"adminactions/", include("adminactions.urls")),
    path(r"power_query/", include("power_query.urls")),
    path(r"sentry_debug/", lambda _: 1 / 0),
]

ok = lambda _: HttpResponse("OK")

urlpatterns = [
    path("api/", include(api_patterns)),
    path("health", ok),
    path("", include(root_patterns)),
]


if settings.DEBUG:  # pragma: no cover
    import debug_toolbar

    urlpatterns += [
        path(r"__debug__/", include(debug_toolbar.urls)),
    ]
