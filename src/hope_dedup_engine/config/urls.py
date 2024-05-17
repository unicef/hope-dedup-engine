from django.conf import settings
from django.conf.urls import include
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

import debug_toolbar

urlpatterns = [
    path(r"admin/", admin.site.urls),
    path(r"security/", include("unicef_security.urls", namespace="security")),
    path(r"social/", include("social_django.urls", namespace="social")),
    path(r"accounts/", include("django.contrib.auth.urls")),
    path(r"adminactions/", include("adminactions.urls")),
    path(r"sentry_debug/", lambda _: 1 / 0),
    path(r"__debug__/", include(debug_toolbar.urls)),
    path(r"", include("hope_dedup_engine.web.urls")),
    path("public_api/", include("hope_dedup_engine.apps.public_api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
