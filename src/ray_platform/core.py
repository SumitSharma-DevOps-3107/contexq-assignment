"""Pure transformation, persistent Iceberg sink, and baseline training."""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pyarrow as pa
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType, LongType, DoubleType
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

FEATURES = ["employees", "company_age", "assets_usd"]
TARGET = "annual_revenue_usd"
SCHEMA = Schema(
    NestedField(1, "canonical_id", StringType(), required=True),
    NestedField(2, "corporate_name", StringType()),
    NestedField(3, "registration_id", StringType()),
    NestedField(4, "country", StringType()),
    NestedField(5, "employees", LongType()),
    NestedField(6, "company_age", LongType()),
    NestedField(7, "assets_usd", DoubleType()),
    NestedField(8, "annual_revenue_usd", DoubleType()),
    identifier_field_ids=[1],
)


def resolve(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for col in ["country", "registration_id"]:
        if frame[col].isna().any() or frame[col].astype(str).str.strip().eq("").any():
            raise ValueError(f"Missing stable identifier: {col}")
        frame[col] = frame[col].str.strip().str.upper()
    if not frame["source"].isin(["financial", "supply"]).all():
        raise ValueError("Unknown source")
    if not np.isfinite(frame[FEATURES + [TARGET]].to_numpy(dtype=float)).all():
        raise ValueError("Missing or non-finite model inputs or revenue")
    if (frame[FEATURES + [TARGET]] < 0).any().any():
        raise ValueError("Negative model inputs or revenue")
    keys = frame["country"] + ":" + frame["registration_id"]
    frame["canonical_id"] = keys.map(lambda x: hashlib.sha256(x.encode()).hexdigest())
    if frame.duplicated(["source", "canonical_id"]).any():
        raise ValueError("Multiple records for the same company within one source")
    return frame


def harmonize(frame: pd.DataFrame) -> pd.DataFrame:
    # Financial is authoritative when the same company is present in both sources.
    frame = frame.assign(priority=frame.source.map({"supply": 0, "financial": 1}))
    frame = frame.sort_values(["canonical_id", "priority"], kind="stable")
    return frame.drop_duplicates("canonical_id", keep="last")[[f.name for f in SCHEMA.fields]]


def commit(frame: pd.DataFrame, root: Path, cloud=None):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if cloud:
        catalog = cloud.catalog()
        namespace = cloud.database
        # Terraform owns the Glue database; the workload cannot create databases.
        catalog.load_namespace_properties(namespace)
    else:
        catalog = SqlCatalog("local", uri=f"sqlite:///{root / 'catalog.db'}",
                             warehouse=(root / "warehouse").as_uri())
        namespace = "corporate"
        catalog.create_namespace_if_not_exists(namespace)
    table = catalog.create_table_if_not_exists(f"{namespace}.registry", schema=SCHEMA)
    arrow = pa.Table.from_pandas(frame, schema=SCHEMA.as_arrow(), preserve_index=False)
    result = table.upsert(arrow, join_cols=["canonical_id"])
    table.refresh()
    return table.scan().to_pandas(), dict(
        inserted=result.rows_inserted, updated=result.rows_updated,
        snapshot_id=table.current_snapshot().snapshot_id)


def train(frame: pd.DataFrame, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    x_train, x_test, y_train, y_test = train_test_split(
        frame[FEATURES], frame[TARGET], test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=80, max_depth=12, n_jobs=1, random_state=42)
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    metrics = dict(mae_usd=mean_absolute_error(y_test, predictions),
                   r2=r2_score(y_test, predictions), train_rows=len(x_train),
                   test_rows=len(x_test), features=FEATURES,
                   sample_prediction_usd=float(predictions[0]))
    joblib.dump(model, output / "model.joblib")
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics
