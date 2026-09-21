from html import unescape

from django.contrib.admin import AdminSite
from django.test import Client
from django.urls import reverse

from hope_dedup_engine.apps.api.admin.encoding.admin import EncodingAdmin
from hope_dedup_engine.apps.api.admin.finding.admin import FindingAdmin
from hope_dedup_engine.apps.api.admin.json_display import (
    format_log,
    format_quality_scores,
    pretty_json,
    quality_thresholds_for_encoding,
)
from hope_dedup_engine.apps.api.models import Encoding, Finding


def test_pretty_json_none() -> None:
    assert pretty_json(None) == "-"


def test_pretty_json_indents_and_escapes() -> None:
    html = pretty_json({"key": "<script>", "nested": {"n": 1}})
    assert '<pre class="hde-json">' in html
    assert "&lt;script&gt;" in html
    assert "<script>" not in html
    unescaped = unescape(html)
    assert '"nested"' in unescaped
    assert '"n": 1' in unescaped


def test_format_log_empty() -> None:
    assert format_log(None) == "-"
    assert format_log([]) == "-"


def test_format_log_non_list() -> None:
    html = format_log({"action": "encode"})
    assert '<pre class="hde-json">' in html
    assert '"action": "encode"' in unescape(html)
    assert "<details" not in html


def test_format_log_non_dict_and_sparse_entries() -> None:
    html = format_log(["plain-text-entry", {"error": "only-error"}, {}])
    assert "plain-text-entry" in html
    assert ">error</summary>" in html
    assert ">entry</summary>" in html


def test_format_log_collapsible_newest_first() -> None:
    html = format_log(
        [
            {"timestamp": "2026-01-01T00:00:00", "action": "encode", "state": "Encoded"},
            {
                "timestamp": "2026-01-02T00:00:00",
                "action": "deduplicate",
                "state": "Deduplication failed",
                "error": "boom <xss>",
            },
        ]
    )
    assert html.count("<details") == 2
    assert "hde-json-log-entry-error" in html
    assert "deduplicate · Deduplication failed · error" in html
    assert "&lt;xss&gt;" in html
    first_details = html[html.index("<details") : html.index("</details>") + len("</details>")]
    assert " open>" in first_details
    assert "deduplicate" in first_details
    assert "encode" not in first_details


def test_format_quality_scores_empty() -> None:
    assert format_quality_scores(None) == "N/A"
    assert format_quality_scores({}) == "N/A"


def test_format_quality_scores_highlights_failures() -> None:
    html = format_quality_scores(
        {"Sharpness": 0.20, "EyesOpen": 0.90, "DynamicRange": None},
        {"Sharpness": 50, "DynamicRange": 40},
    )
    rows = html.split("<tr")
    sharpness = next(row for row in rows if ">Sharpness</td>" in row)
    eyes = next(row for row in rows if ">EyesOpen</td>" in row)
    dynamic_range = next(row for row in rows if ">DynamicRange</td>" in row)

    assert "hde-quality-score-fail" in sharpness
    assert "Failed" in sharpness
    assert "0.20" in sharpness
    assert "0.50" in sharpness

    assert "hde-quality-score-fail" not in eyes
    assert "Failed" not in eyes
    assert "Passed" not in eyes

    assert "hde-quality-score-fail" in dynamic_range
    assert "Failed" in dynamic_range


def test_quality_thresholds_for_encoding_ignores_non_dict_settings(mocker) -> None:
    encoding = mocker.Mock(spec=Encoding, image_quality_scores={"Sharpness": 0.2})
    assert quality_thresholds_for_encoding(encoding) == {}


def test_quality_thresholds_for_encoding_missing_relations() -> None:
    assert quality_thresholds_for_encoding(type("Encoding", (), {"deduplication_set": None})()) == {}
    assert (
        quality_thresholds_for_encoding(
            type("Encoding", (), {"deduplication_set": type("DS", (), {"group": None})()})()
        )
        == {}
    )


def test_deduplication_set_change_form_renders_collapsible_log(
    admin_client: Client,
    deduplication_set,
) -> None:
    deduplication_set.log = [
        {"timestamp": "2026-01-01T00:00:00", "action": "encode", "state": "Encoded"},
        {"timestamp": "2026-01-02T00:00:00", "action": "deduplicate", "state": "Deduplicated"},
    ]
    deduplication_set.save(update_fields=["log"])

    response = admin_client.get(reverse("admin:api_deduplicationset_change", args=[deduplication_set.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    assert 'class="hde-json-log"' in content
    assert content.count("<details") == 2
    assert "deduplicate" in content
    assert '"action": "encode"' in unescape(content)


def test_finding_change_form_renders_formatted_config(admin_client: Client, finding: Finding) -> None:
    finding.config = {"recognition_model": "Facenet512", "sharpness_threshold": 0.5}
    finding.save(update_fields=["config"])

    response = admin_client.get(reverse("admin:api_finding_change", args=[finding.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    assert '<pre class="hde-json">' in content
    assert "Facenet512" in content
    assert "sharpness_threshold" in content


def test_finding_admin_config_method() -> None:
    admin = FindingAdmin(Finding, AdminSite())
    finding = Finding(config={"distance_metric": "cosine"})
    html = admin.formatted_config(finding)
    assert '<pre class="hde-json">' in html
    assert "cosine" in html
    assert admin.formatted_config(Finding(config=None)) == "-"


def test_encoding_change_form_renders_failed_quality_scores(
    admin_client: Client,
    encoding: Encoding,
) -> None:
    encoding.deduplication_set.group.settings = {"sharpness_threshold": 0.5}
    encoding.deduplication_set.group.save(update_fields=["settings"])
    encoding.image_quality_scores = {"Sharpness": 0.2, "EyesOpen": 0.9}
    encoding.save(update_fields=["image_quality_scores"])

    response = admin_client.get(reverse("admin:api_encoding_change", args=[encoding.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    assert "hde-quality-scores" in content
    assert "hde-quality-score-fail" in content
    assert "Failed" in content
    assert "EyesOpen" in content


def test_encoding_admin_highlights_failed_scores(encoding: Encoding) -> None:
    encoding.deduplication_set.group.settings = {"sharpness_threshold": 0.5, "eyes_open_threshold": 0.4}
    encoding.image_quality_scores = {"Sharpness": 0.2, "EyesOpen": 0.9}
    admin = EncodingAdmin(Encoding, AdminSite())

    html = admin.image_quality_scores_sorted(encoding)

    assert "hde-quality-score-fail" in html
    assert "Failed" in html
    assert "Passed" in html
    assert quality_thresholds_for_encoding(encoding) == {"Sharpness": 50.0, "EyesOpen": 40.0}
