import pandas as pd
import pytest

from ray_platform.datasets import generate
from ray_platform.core import resolve, harmonize, commit, train


@pytest.fixture
def sources(tmp_path):
    generate(tmp_path)
    a = pd.read_csv(tmp_path / "supply.csv")
    b = pd.read_csv(tmp_path / "financial.csv")
    assert len(a) == len(b) == 1200
    return pd.concat([a, b], ignore_index=True)


def test_resolution_and_source_precedence(sources):
    sources.loc[sources.source == "financial", "annual_revenue_usd"] = 123.0
    canonical = harmonize(resolve(sources))
    assert len(canonical) == 1800
    assert canonical.canonical_id.nunique() == 1800
    assert canonical.loc[canonical.registration_id == "REG-000700", "annual_revenue_usd"].item() == 123
    shuffled = harmonize(resolve(sources.sample(frac=1, random_state=9)))
    pd.testing.assert_frame_equal(canonical.reset_index(drop=True), shuffled.reset_index(drop=True))


def test_invalid_identity_rejected(sources):
    sources.loc[0, "registration_id"] = " "
    with pytest.raises(ValueError, match="Missing stable identifier"):
        resolve(sources)


def test_ambiguous_source_record_rejected(sources):
    with pytest.raises(ValueError, match="Multiple records"):
        resolve(pd.concat([sources, sources.iloc[[0]]]))


def test_same_registration_in_different_country_stays_separate(sources):
    extra = sources.iloc[[0]].copy()
    extra["country"] = "US"
    assert len(harmonize(resolve(pd.concat([sources, extra])))) == 1801


def test_iceberg_rerun_update_and_training(sources, tmp_path):
    canonical = harmonize(resolve(sources))
    persisted, first = commit(canonical, tmp_path)
    assert first["inserted"] == 1800
    persisted, second = commit(canonical, tmp_path)
    assert second["inserted"] == second["updated"] == 0
    canonical.iloc[0, canonical.columns.get_loc("annual_revenue_usd")] += 1000
    persisted, third = commit(canonical, tmp_path)
    assert third["updated"] == 1
    assert len(persisted) == 1800
    metrics = train(persisted, tmp_path / "model")
    assert metrics["r2"] > 0.9
    assert metrics["train_rows"] + metrics["test_rows"] == 1800
    assert (tmp_path / "model/model.joblib").exists()
