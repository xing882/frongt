from __future__ import annotations

import functools
from datetime import datetime
from typing import Any

import pandas as pd

from app.config import settings


@functools.lru_cache(maxsize=1)
def load_energy() -> pd.DataFrame:
    df = pd.read_csv(settings.energy_csv, encoding="utf-8-sig")
    df["monitor_time"] = pd.to_datetime(df["monitor_time"])
    return df


@functools.lru_cache(maxsize=1)
def load_metadata() -> pd.DataFrame:
    return pd.read_csv(settings.metadata_csv, encoding="utf-8-sig")


def query_energy(
    building_id: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
    offset: int = 0,
    limit: int = 500,
    sort_by: str | None = "monitor_time",
    sort_desc: bool = False,
) -> tuple[int, list[dict[str, Any]]]:
    df = load_energy()
    if building_id:
        df = df[df["building_id"] == building_id]
    if time_from:
        df = df[df["monitor_time"] >= pd.to_datetime(time_from)]
    if time_to:
        df = df[df["monitor_time"] <= pd.to_datetime(time_to)]
    total = int(len(df))
    if total == 0:
        return 0, []
    sort_col = sort_by if sort_by and sort_by in df.columns else "monitor_time"
    ascending = not sort_desc
    try:
        df = df.sort_values(sort_col, ascending=ascending, na_position="last")
    except Exception:
        df = df.sort_values("monitor_time", ascending=not sort_desc, na_position="last")
    if offset:
        df = df.iloc[offset:]
    if limit > 0:
        df = df.iloc[:limit]
    out = df.copy()
    out["monitor_time"] = out["monitor_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return total, out.fillna("").to_dict(orient="records")


def list_buildings() -> list[dict[str, Any]]:
    meta = load_metadata()
    return meta.fillna("").to_dict(orient="records")
