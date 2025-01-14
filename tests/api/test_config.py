import json

from django.contrib.messages import get_messages
from django.urls import reverse

from factory import fuzzy
from testutils.factories.api import ConfigFactory, DeduplicationSetFactory


def test_response_change_redirects_to_confirm_save_if_related_objects_exist(
    admin_client,
):
    config_instance = ConfigFactory.create()
    deduplication_sets = DeduplicationSetFactory.create_batch(2, config=config_instance)
    change_url = reverse("admin:api_config_change", args=[config_instance.pk])
    confirm_url = reverse("admin:confirm_save_config", args=[config_instance.pk])
    form_data = {
        "name": "Updated Config",
        "settings": json.dumps(
            {"detection": {"confidence": fuzzy.FuzzyFloat(0.1, 1.0).fuzz()}}
        ),
    }

    response = admin_client.post(change_url, form_data)
    assert response.status_code == 302
    assert response.url == confirm_url

    response = admin_client.get(confirm_url)
    assert response.status_code == 200
    assert response.wsgi_request.path == confirm_url

    messages = [str(msg) for msg in get_messages(response.context["request"])]
    assert all(
        any(str(dd_set) in msg for msg in messages) for dd_set in deduplication_sets
    )
