from __future__ import annotations

import hashlib
import json
import math
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = PACKAGE_ROOT.parent
SCHEMA_PATH = PACKAGE_ROOT / "P3_CULTURE_SCHEMA_REGISTRY_v1.0.json"
IMPLEMENTED_SCHEMA_PATH = PACKAGE_ROOT / "P3_CULTURE_SCHEMA_REGISTRY_v1.1_IMPLEMENTED.json"
CONFIG_PATH = PACKAGE_ROOT / "config" / "pipeline_config.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def short_hash(value: str, n: int = 8) -> str:
    return sha256_text(value)[:n].upper()


def normalize_text(text: Any) -> str:
    if text is None or text is pd.NA or (isinstance(text, float) and math.isnan(text)):
        return ""
    value = unicodedata.normalize("NFKC", str(text)).replace("\x00", "")
    value = re.sub(r"[\r\n]+", " ", value)
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip()


def compact_text(text: Any) -> str:
    return re.sub(r"\s+", "", normalize_text(text))


def nullable_text(text: Any) -> Any:
    value = normalize_text(text)
    if not value or value.lower() == "null":
        return pd.NA
    return value


def meeting_date_iso(year_2digit: Any, mmdd: Any):
    try:
        year = 2000 + int(str(year_2digit))
        digits = re.sub(r"\D", "", str(mmdd)).zfill(4)
        return datetime(year, int(digits[:2]), int(digits[2:4])).date()
    except Exception:
        return pd.NaT


def safe_git_head(cwd: Path) -> str | None:
    import subprocess

    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=cwd, check=True, capture_output=True, text=True
        ).stdout.strip()
    except Exception:
        return None


LAYER_DIR = {
    "L0_governance": "governance",
    "L1_canonical": "canonical",
    "L2_target": "target",
    "L2_retrieval": "retrieval",
    "L3_qa_behavior": "qa",
    "L4_vector": "embeddings",
    "L4_visual": "projection",
    "L5_editorial": "editorial",
    "L6_frontend": "frontend",
}


class SchemaRegistry:
    def __init__(self, path: Path = SCHEMA_PATH):
        self.path = path
        self.payload = json.loads(path.read_text(encoding="utf-8"))
        self.entities = {item["name"]: item for item in self.payload["entities"]}

    def columns(self, name: str) -> list[str]:
        return [column["name"] for column in self.entities[name]["columns"]]

    def layer(self, name: str) -> str:
        return self.entities[name]["layer"]

    def empty(self, name: str) -> pd.DataFrame:
        return pd.DataFrame(columns=self.columns(name))

    def conform(self, name: str, df: pd.DataFrame, *, exact: bool = True) -> pd.DataFrame:
        entity = self.entities[name]
        out = df.copy()
        for spec in entity["columns"]:
            col = spec["name"]
            if col not in out:
                out[col] = pd.NA
            dtype = spec["dtype"]
            try:
                if dtype == "string" or dtype == "category":
                    out[col] = out[col].astype("string")
                elif dtype == "Int64":
                    out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")
                elif dtype == "Float64":
                    out[col] = pd.to_numeric(out[col], errors="coerce").astype("Float64")
                elif dtype == "boolean":
                    out[col] = out[col].astype("boolean")
                elif dtype.startswith("timestamp"):
                    out[col] = pd.to_datetime(out[col], errors="coerce", utc=True)
                elif dtype == "date32":
                    out[col] = pd.to_datetime(out[col], errors="coerce").dt.date
            except (TypeError, ValueError):
                pass
        cols = self.columns(name)
        if exact:
            return out[cols]
        return out[cols + [c for c in out.columns if c not in cols]]

    def output_path(self, name: str) -> Path:
        directory = LAYER_DIR[self.layer(name)]
        return PACKAGE_ROOT / "data" / directory / f"{name}.parquet"

    def save(self, name: str, df: pd.DataFrame, *, exact: bool = True) -> Path:
        path = self.output_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conform(name, df, exact=exact).to_parquet(path, index=False)
        return path


@dataclass
class AuditTrail:
    run_id: str
    metrics: list[dict[str, Any]] = field(default_factory=list)
    anomalies: list[dict[str, Any]] = field(default_factory=list)

    def metric(
        self,
        entity: str,
        name: str,
        value: float | None,
        status: str,
        threshold: str,
        detail: str = "",
        severity: str = "info",
        text: str | None = None,
    ) -> None:
        seq = len(self.metrics) + 1
        self.metrics.append(
            {
                "quality_metric_id": f"DQ_{self.run_id}_{seq:04d}",
                "pipeline_run_id": self.run_id,
                "entity_name": entity,
                "entity_scope_id": pd.NA,
                "metric_name": name,
                "metric_value": value,
                "metric_text": text,
                "expected_value": threshold,
                "threshold": threshold,
                "quality_status": status,
                "severity": severity,
                "detail": detail,
                "sample_count": pd.NA,
                "sample_path": pd.NA,
            }
        )

    def anomaly(
        self,
        entity: str,
        entity_id: str | None,
        anomaly_type: str,
        severity: str,
        detail: str,
        preview: str = "",
        source_path: str = "",
    ) -> None:
        seq = len(self.anomalies) + 1
        self.anomalies.append(
            {
                "anomaly_id": f"ANOM_{self.run_id}_{seq:05d}",
                "pipeline_run_id": self.run_id,
                "entity_name": entity,
                "entity_id": entity_id,
                "anomaly_type": anomaly_type,
                "severity": severity,
                "detail": detail,
                "text_preview": normalize_text(preview)[:300] or pd.NA,
                "source_path": source_path or pd.NA,
                "detected_at": utc_now(),
                "resolution_status": "open",
                "resolution_note": pd.NA,
            }
        )


def save_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def save_csv(path: Path, df: pd.DataFrame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path

