import pytest

from ray_platform.cloud import CloudSettings


def test_local_remains_default(monkeypatch):
    monkeypatch.delenv("CATALOG_TYPE", raising=False)
    assert CloudSettings.from_env() is None


def test_cloud_fails_closed_on_incomplete_config(monkeypatch):
    monkeypatch.setenv("CATALOG_TYPE", "glue")
    monkeypatch.delenv("S3_BUCKET", raising=False)
    with pytest.raises(ValueError, match="Glue mode requires"):
        CloudSettings.from_env()


def test_cloud_uses_separate_input_warehouse_and_artifact_prefixes(monkeypatch):
    for k,v in {"CATALOG_TYPE":"glue", "S3_BUCKET":"example-assignment-data", "AWS_REGION":"us-east-1", "GLUE_DATABASE":"ray_assignment"}.items():
        monkeypatch.setenv(k,v)
    config = CloudSettings.from_env()
    assert config.inputs == ["s3://example-assignment-data/input/supply.csv", "s3://example-assignment-data/input/financial.csv"]
    assert config.warehouse == "s3://example-assignment-data/warehouse/"


def test_typo_cannot_fall_back_to_local_storage(monkeypatch):
    monkeypatch.setenv("CATALOG_TYPE", "gule")
    with pytest.raises(ValueError, match="CATALOG_TYPE"):
        CloudSettings.from_env()
