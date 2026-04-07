from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.services import energy_store

router = APIRouter(prefix="/energy", tags=["energy"])


@router.get("/buildings")
def list_buildings() -> dict[str, Any]:
    return {"items": energy_store.list_buildings()}


@router.get("/records")
def query_records(
    building_id: str | None = Query(None),
    time_from: str | None = Query(None, description="含该时刻，如 2016-01-02 17:00:00"),
    time_to: str | None = Query(None),
    offset: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(500, ge=1, le=10000),
    sort_by: str | None = Query("monitor_time", description="排序列名，须为数据表列"),
    sort_order: str = Query("asc", description="asc 或 desc"),
) -> dict[str, Any]:
    sort_desc = sort_order.lower() == "desc"
    total, rows = energy_store.query_energy(
        building_id=building_id,
        time_from=time_from,
        time_to=time_to,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )
    return {"total": total, "count": len(rows), "items": rows}
