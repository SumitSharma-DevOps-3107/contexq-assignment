"""AWS configuration; credentials come only from the SDK/IRSA provider chain."""
import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CloudSettings:
    bucket: str
    region: str
    database: str

    @classmethod
    def from_env(cls):
        mode = os.getenv("CATALOG_TYPE", "local")
        if mode == "local":
            return None
        if mode != "glue":
            raise ValueError("CATALOG_TYPE must be local or glue")
        fields = {name: os.getenv(name, "") for name in ("S3_BUCKET", "AWS_REGION", "GLUE_DATABASE")}
        if not all(fields.values()):
            raise ValueError("Glue mode requires S3_BUCKET, AWS_REGION and GLUE_DATABASE")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", fields["S3_BUCKET"]):
            raise ValueError("Invalid S3 bucket name")
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", fields["GLUE_DATABASE"]):
            raise ValueError("Invalid Glue database name")
        return cls(fields["S3_BUCKET"], fields["AWS_REGION"], fields["GLUE_DATABASE"])

    @property
    def warehouse(self):
        return f"s3://{self.bucket}/warehouse/"

    @property
    def inputs(self):
        return [f"s3://{self.bucket}/input/{name}.csv" for name in ("supply", "financial")]

    def catalog(self):
        from pyiceberg.catalog.glue import GlueCatalog
        return GlueCatalog("aws", **{
            "warehouse": self.warehouse,
            "client.region": self.region,
            "glue.region": self.region,
            "s3.region": self.region,
        })

    def publish(self, root: Path, run_id: str):
        import boto3
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id):
            raise ValueError("Invalid run ID")
        client = boto3.client("s3", region_name=self.region)
        for relative in ("model/model.joblib", "model/metrics.json", "run.json"):
            client.upload_file(str(root / relative), self.bucket, f"artifacts/{run_id}/{relative}")
        return f"s3://{self.bucket}/artifacts/{run_id}/"
