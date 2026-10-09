from django.urls import path

from hope_dedup_engine.apps.biographic.views import (
    DatasetApproveView,
    DatasetCreateView,
    DatasetFindingsView,
    DatasetProcessView,
    DatasetRejectView,
)

urlpatterns = [
    path(
        "biographic/<str:business_area_slug>/<str:program_id>/datasets/",
        DatasetCreateView.as_view(),
        name="biographic-datasets",
    ),
    path(
        "biographic/<str:business_area_slug>/<str:program_id>/datasets/<int:dataset_id>/process/",
        DatasetProcessView.as_view(),
        name="biographic-dataset-process",
    ),
    path(
        "biographic/<str:business_area_slug>/<str:program_id>/datasets/<int:dataset_id>/biographic_findings/",
        DatasetFindingsView.as_view(),
        name="biographic-dataset-findings",
    ),
    path(
        "biographic/<str:business_area_slug>/<str:program_id>/datasets/<int:dataset_id>/approve/",
        DatasetApproveView.as_view(),
        name="biographic-dataset-approve",
    ),
    path(
        "biographic/<str:business_area_slug>/<str:program_id>/datasets/<int:dataset_id>/reject/",
        DatasetRejectView.as_view(),
        name="biographic-dataset-reject",
    ),
]
