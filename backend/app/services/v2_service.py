from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.energy_store import load_energy

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

_YOLO_MODEL = None
_YOLO_MODEL_NAME = "yolov8n-seg.pt"

# YOLO-World v2：开放词汇，可一次设定大量室内类别（需 ultralytics>=8.3 推荐）
_YOLO_WORLD_MODEL = None
_YOLO_WORLD_MODEL_NAME = "yolov8m-worldv2.pt"

# ultralytics 默认复用 model.predictor；多请求并发或 YOLO-World 动态 set_classes 后不复位会导致「只第一次识别正常」
_YOLO_INFER_LOCK = threading.Lock()


def _reset_ultralytics_predictor(m: Any) -> None:
    if m is not None:
        m.predictor = None

# 默认英文类名（逗号分隔可扩展）；用户可通过 query prompt 覆盖
_INDOOR_CLASSES_DEFAULT: tuple[str, ...] = (
    "person",
    "bed",
    "sofa",
    "couch",
    "chair",
    "bench",
    "stool",
    "dining table",
    "coffee table",
    "desk",
    "nightstand",
    "tv",
    "monitor",
    "laptop",
    "keyboard",
    "mouse",
    "book",
    "shelf",
    "bookshelf",
    "cabinet",
    "wardrobe",
    "refrigerator",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "bathtub",
    "toilet",
    "shower",
    "lamp",
    "light",
    "ceiling fan",
    "fan",
    "air conditioner",
    "radiator",
    "curtain",
    "blinds",
    "potted plant",
    "vase",
    "clock",
    "mirror",
    "picture frame",
    "rug",
    "carpet",
    "pillow",
    "blanket",
    "door",
    "window",
    "trash can",
    "vacuum cleaner",
    "backpack",
    "handbag",
    "bottle",
    "cup",
    "bowl",
    "remote",
    "cell phone",
)

# YOLO-World 一次挂太多类名时召回可能很差；零结果时自动用少量常见类重试
_INDOOR_CLASSES_FALLBACK: tuple[str, ...] = (
    "person",
    "chair",
    "desk",
    "table",
    "dining table",
    "monitor",
    "laptop",
    "keyboard",
    "window",
    "door",
    "lamp",
    "light",
    "sofa",
    "cabinet",
    "book",
)


def vision_analyze(filename: str | None = None) -> dict[str, Any]:
    """
    演示级视觉分析（文件名启发）；上传接口可叠加 YOLOv8 检测。
    """
    name = (filename or "").lower()
    room_type = "office"
    if "meeting" in name or "会议" in name:
        room_type = "meeting_room"
    elif "机房" in name or "server" in name:
        room_type = "server_room"

    return {
        "room_type": room_type,
        "people_count": 0 if "empty" in name else 3,
        "density": 0.12 if "empty" in name else 0.55,
        "devices": {"ac_on": True, "lights_on": True, "pc_on": True},
        "lighting_level": "normal",
        "curtain_state": "half_open",
        "confidence": 0.86,
        "note": "文件名规则为演示占位；上传图片时可叠加 YOLOv8 / YOLO-World（pip install ultralytics）",
    }


def _parse_indoor_classes(prompt: str | None) -> list[str]:
    if prompt and prompt.strip():
        parts = [p.strip() for p in prompt.replace("，", ",").split(",")]
        out = [p for p in parts if p]
        return out[:120]
    return list(_INDOOR_CLASSES_DEFAULT)


def _tensor_item(x: Any) -> float | int:
    """标量 tensor / numpy -> Python 数值。"""
    try:
        if hasattr(x, "detach"):
            return float(x.detach().cpu().numpy().reshape(-1)[0])
        if hasattr(x, "item"):
            return x.item()
    except Exception:
        pass
    return float(x)


def _boxes_and_masks_from_result(r0: Any) -> tuple[dict[str, int], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    解析 ultralytics Result。YOLO-World / 新版 tensor API 下批量 .tolist() 可能异常，
    若整段失败会导致「count>0 但 boxes 空」；改为逐框索引解析。
    """
    counts: dict[str, int] = {}
    boxes_out: list[dict[str, Any]] = []
    masks_out: list[dict[str, Any]] = []
    bx = getattr(r0, "boxes", None)
    if bx is None:
        return counts, boxes_out, masks_out
    try:
        n = len(bx)
    except Exception:
        return counts, boxes_out, masks_out
    if n <= 0:
        return counts, boxes_out, masks_out

    names = getattr(r0, "names", None) or {}

    # 优先用 Boxes.data（N×6：xyxy + conf + cls），与 ultralytics 内部一致，最稳
    data = getattr(bx, "data", None)
    if data is not None:
        try:
            arr = data.detach().cpu().numpy() if hasattr(data, "detach") else data.cpu().numpy()
            if arr is not None and getattr(arr, "size", 0) > 0:
                arr = arr.reshape(-1, arr.shape[-1]) if arr.ndim > 1 else arr.reshape(1, -1)
                for row in arr[:200]:
                    flat = row.reshape(-1)
                    if flat.size < 6:
                        continue
                    x1, y1, x2, y2 = float(flat[0]), float(flat[1]), float(flat[2]), float(flat[3])
                    conf_v = float(flat[4])
                    ci = int(flat[5])
                    label = str(names.get(ci, ci))
                    counts[label] = counts.get(label, 0) + 1
                    boxes_out.append(
                        {
                            "label": label,
                            "conf": conf_v,
                            "bbox_xyxy": [x1, y1, x2, y2],
                        }
                    )
        except Exception:
            counts = {}
            boxes_out = []

    if not boxes_out:
        for i in range(min(n, 200)):
            try:
                row = bx.xyxy[i]
                if hasattr(row, "cpu"):
                    row = row.cpu().detach().numpy().ravel()
                elif hasattr(row, "numpy"):
                    row = row.numpy().ravel()
                else:
                    row = row
                coords = [float(x) for x in (row.tolist() if hasattr(row, "tolist") else list(row))]
                if len(coords) < 4:
                    continue
                x1, y1, x2, y2 = coords[0], coords[1], coords[2], coords[3]

                ci_raw = bx.cls[i]
                ci = int(_tensor_item(ci_raw))
                label = str(names.get(ci, ci))

                conf: float | None = None
                if getattr(bx, "conf", None) is not None:
                    try:
                        conf = float(_tensor_item(bx.conf[i]))
                    except Exception:
                        conf = None

                counts[label] = counts.get(label, 0) + 1
                boxes_out.append(
                    {
                        "label": label,
                        "conf": conf,
                        "bbox_xyxy": [x1, y1, x2, y2],
                    }
                )
            except Exception:
                continue

    try:
        if getattr(r0, "masks", None) is not None and getattr(r0.masks, "xy", None) is not None:
            for i, poly in enumerate(r0.masks.xy[:80]):
                if i >= len(boxes_out):
                    break
                pts = [[float(x), float(y)] for x, y in poly.tolist()] if hasattr(poly, "tolist") else []
                if not pts:
                    continue
                masks_out.append({"i": i, "label": boxes_out[i]["label"], "polygon_xy": pts[:200]})
    except Exception:
        masks_out = []
    return counts, boxes_out, masks_out


def _run_yolo(path: Path) -> dict[str, Any]:
    global _YOLO_MODEL
    try:
        from ultralytics import YOLO
    except ImportError:
        return {"available": False, "hint": "可选依赖：pip install ultralytics（将下载 yolov8n 权重）"}

    with _YOLO_INFER_LOCK:
        if _YOLO_MODEL is None:
            # Use segmentation model to get masks for better layout extraction
            _YOLO_MODEL = YOLO(_YOLO_MODEL_NAME)
        _reset_ultralytics_predictor(_YOLO_MODEL)
        # For "layout-style" images, lower conf + larger imgsz helps recall.
        results = _YOLO_MODEL.predict(str(path), verbose=False, conf=0.15, iou=0.6, imgsz=1024)
        if not results:
            return {"available": True, "detections": {}, "count": 0, "boxes": [], "image_size": None}
        r0 = results[0]
        counts, boxes_out, masks_out = _boxes_and_masks_from_result(r0)
        image_size = None
        try:
            if getattr(r0, "orig_shape", None):
                oh, ow = r0.orig_shape
                image_size = {"w": int(ow), "h": int(oh)}
        except Exception:
            image_size = None
        # 与 boxes_out 一致，避免解析失败时 len(r0.boxes)>0 但 boxes 为空
        cnt = len(boxes_out)
        return {
            "available": True,
            "pipeline": "yolo_seg",
            "model": _YOLO_MODEL_NAME,
            "detections": counts,
            "count": cnt,
            "boxes": boxes_out[:80],
            "masks": masks_out,
            "image_size": image_size,
        }


def _orig_shape_from_result(r0: Any) -> dict[str, int] | None:
    try:
        if getattr(r0, "orig_shape", None):
            oh, ow = r0.orig_shape
            return {"w": int(ow), "h": int(oh)}
    except Exception:
        pass
    return None


def _run_yolo_world(path: Path, prompt: str | None, conf: float | None = None) -> dict[str, Any]:
    """
    Ultralytics YOLO-World：开放词汇检测，室内场景可一次设定大量英文类名。
    每次请求都会 predict 当前上传文件；模型实例全局缓存仅为省加载时间，不缓存图像结果。
    参考：https://docs.ultralytics.com/models/yolo-world/
    """
    global _YOLO_WORLD_MODEL
    try:
        from ultralytics import YOLO
    except ImportError:
        return {"available": False, "hint": "可选依赖：pip install 'ultralytics>=8.3'（将自动下载 yolov8m-worldv2.pt）"}

    base_conf = 0.12 if conf is None else max(0.02, min(0.95, float(conf)))

    user_classes = _parse_indoor_classes(prompt)
    if not user_classes:
        user_classes = list(_INDOOR_CLASSES_DEFAULT)

    with _YOLO_INFER_LOCK:
        if _YOLO_WORLD_MODEL is None:
            try:
                _YOLO_WORLD_MODEL = YOLO(_YOLO_WORLD_MODEL_NAME)
            except Exception as e:
                msg = str(e)
                if len(msg) > 500:
                    msg = msg[:500] + "..."
                return {
                    "available": False,
                    "hint": "加载 YOLO-World 权重失败（需联网首次下载，或升级 ultralytics：pip install -U ultralytics）",
                    "error": msg,
                    "model": _YOLO_WORLD_MODEL_NAME,
                }

        return _run_yolo_world_core(path, user_classes, base_conf)


def _run_yolo_world_core(path: Path, user_classes: list[str], base_conf: float) -> dict[str, Any]:
    """在 _YOLO_INFER_LOCK 内调用；set_classes 后必须 reset predictor，否则 ultralytics 复用 AutoBackend 时常见只认第一次图源。"""
    global _YOLO_WORLD_MODEL

    # 多轮：全量类 + 用户 conf → 更低 conf → 少量常见类（一次挂太多英文类 YOLO-World 常全空）
    attempts: list[tuple[str, list[str], float]] = [
        ("default", user_classes, base_conf),
        ("low_conf", user_classes, min(base_conf, 0.05)),
        ("fallback_classes", list(_INDOOR_CLASSES_FALLBACK), 0.08),
    ]

    r0: Any = None
    counts: dict[str, int] = {}
    boxes_out: list[dict[str, Any]] = []
    masks_out: list[dict[str, Any]] = []
    image_size: dict[str, int] | None = None
    classes_used: list[str] = user_classes
    tried: list[str] = []
    last_conf = base_conf

    for tag, cls_list, cf in attempts:
        last_conf = cf
        try:
            _YOLO_WORLD_MODEL.set_classes(cls_list)
        except Exception as e:
            msg = str(e)
            if len(msg) > 500:
                msg = msg[:500] + "..."
            if tag == "default":
                hint = "set_classes 失败：请升级 ultralytics 至 8.3.155+（YOLO-World 动态类别修复）"
                low = msg.lower()
                if "no module named 'clip'" in low or "modulenotfounderror" in low and "clip" in low:
                    hint = (
                        "YOLO-World 需要 OpenAI CLIP（import clip）。请安装："
                        "pip install git+https://github.com/openai/CLIP.git"
                        "（或 pip install -r backend/requirements-v2-vision.txt），然后重启后端。"
                    )
                return {
                    "available": False,
                    "hint": hint,
                    "error": msg,
                    "model": _YOLO_WORLD_MODEL_NAME,
                    "classes_preview": cls_list[:30],
                }
            tried.append(f"{tag}:set_classes_failed")
            continue

        _reset_ultralytics_predictor(_YOLO_WORLD_MODEL)

        try:
            results = _YOLO_WORLD_MODEL.predict(
                str(path),
                verbose=False,
                conf=cf,
                iou=0.5,
                imgsz=1024,
                max_det=150,
            )
        except Exception as e:
            msg = str(e)
            if len(msg) > 500:
                msg = msg[:500] + "..."
            if tag == "default":
                return {
                    "available": False,
                    "hint": "YOLO-World 推理失败",
                    "error": msg,
                    "model": _YOLO_WORLD_MODEL_NAME,
                    "classes_preview": cls_list[:30],
                }
            tried.append(f"{tag}:predict_failed")
            continue

        if not results:
            tried.append(f"{tag}:empty_results")
            continue

        r0 = results[0]
        counts, boxes_out, masks_out = _boxes_and_masks_from_result(r0)
        image_size = _orig_shape_from_result(r0)
        classes_used = cls_list
        tried.append(f"{tag}:conf={cf:.3f}:parsed_boxes={len(boxes_out)}")
        if len(boxes_out) > 0:
            break

    if r0 is None:
        return {
            "available": True,
            "pipeline": "yolo_world",
            "model": _YOLO_WORLD_MODEL_NAME,
            "detections": {},
            "count": 0,
            "boxes": [],
            "masks": [],
            "image_size": None,
            "classes_used": user_classes,
            "conf_used": last_conf,
            "inference_attempts": tried,
            "note": "无检测结果：已重试更低置信度与精简类别；可传 conf=0.05 或 mode=yolo_seg 试分割模型。",
        }

    cnt = len(boxes_out)
    note = (
        "YOLO-World：开放词汇；prompt 为空时使用内置室内类别表。"
        " 每次上传独立推理；全局仅缓存模型权重；set_classes 后会重建 predictor。"
    )
    if tried:
        note += f" 推理记录: {' | '.join(tried)}。"

    return {
        "available": True,
        "pipeline": "yolo_world",
        "model": _YOLO_WORLD_MODEL_NAME,
        "detections": counts,
        "count": cnt,
        "boxes": boxes_out[:120],
        "masks": masks_out,
        "image_size": image_size,
        "classes_used": classes_used,
        "conf_used": last_conf,
        "inference_attempts": tried,
        "note": note.strip(),
    }


def vision_analyze_saved(
    saved_path: Path,
    original_name: str,
    mode: str = "yolo_world",
    prompt: str | None = None,
    conf: float | None = None,
) -> dict[str, Any]:
    out = vision_analyze(filename=original_name)
    out["saved_path"] = str(saved_path).replace("\\", "/")
    try:
        if mode == "yolo_world":
            out["yolo"] = _run_yolo_world(saved_path, prompt, conf=conf)
        else:
            out["yolo"] = _run_yolo(saved_path)
    except Exception as e:
        msg = str(e)
        if len(msg) > 1200:
            msg = msg[:1200] + "..."
        out["yolo"] = {
            "available": False,
            "hint": "视觉推理未捕获异常已转为 JSON（请查看 error）。常见原因：GPU/内存不足、ultralytics 版本与权重不兼容。",
            "error": msg,
        }
    yl = out.get("yolo") or {}
    people_like = 0
    if isinstance(yl.get("detections"), dict):
        for k in ("person", "people"):
            v = yl["detections"].get(k, 0)
            try:
                people_like += int(v)
            except (TypeError, ValueError):
                pass
    if yl.get("available") and people_like:
        out["people_count"] = int(people_like)
        out["density"] = min(1.0, 0.15 + 0.05 * people_like)
    return out


def twin_scene(building_id: str | None = None) -> dict[str, Any]:
    df = load_energy().copy()
    if building_id:
        df = df[df["building_id"] == building_id]
    if df.empty:
        return {"building_id": building_id, "floors": [], "legend": _legend()}

    df = df.sort_values("monitor_time")
    bid_last = str(df["building_id"].iloc[-1])
    sub = df[df["building_id"] == bid_last] if not building_id else df
    sub = sub.tail(min(400, len(sub)))
    n = min(5, max(3, max(1, len(sub) // 80)))
    step = max(1, len(sub) // n)
    floors: list[dict[str, Any]] = []
    for i in range(n):
        part = sub.iloc[i * step : (i + 1) * step if i < n - 1 else len(sub)]
        if part.empty:
            continue
        elec = float(pd.to_numeric(part["electricity_kwh"], errors="coerce").mean() or 0.0)
        if elec > 40:
            status = "high"
        elif elec > 20:
            status = "warning"
        else:
            status = "normal"
        floors.append(
            {
                "floor": i + 1,
                "room_id": f"F{i + 1:02d}-R01",
                "building_id": bid_last,
                "electricity_kwh": round(elec, 3),
                "status": status,
            }
        )
    return {"building_id": building_id or bid_last, "floors": floors, "legend": _legend()}


def ops_indicators(building_id: str | None = None) -> dict[str, Any]:
    df = load_energy().copy()
    if building_id:
        df = df[df["building_id"] == building_id]
    if df.empty:
        return {"rows": 0, "indicators": {"ewi": None, "su": None, "dh": None}}

    e = pd.to_numeric(df.get("electricity_kwh"), errors="coerce")
    base = max(float(e.quantile(0.3)) if e.notna().any() else 1.0, 1e-6)
    monitor = pd.to_datetime(df["monitor_time"])
    night_ratio = float(((monitor.dt.hour <= 5).sum()) / max(len(df), 1))
    ewi = float((e.mean() / base) * night_ratio) if e.notna().any() else None

    day_ratio = float(((monitor.dt.hour >= 8) & (monitor.dt.hour <= 20)).sum()) / max(len(df), 1)
    su = float(day_ratio * 0.62)

    dh = float(max(0.0, 1.0 - night_ratio * 0.35))
    return {
        "rows": int(len(df)),
        "indicators": {"ewi": round(ewi, 4) if ewi is not None else None, "su": round(su, 4), "dh": round(dh, 4)},
        "formula_hint": {
            "ewi": "(实际能耗/基准能耗) * 无人时长占比(近似)",
            "su": "(实际使用时长/可使用时长) * 平均人员密度(近似)",
            "dh": "1 - (故障次数*平均修复时间)/总运行时间(演示近似)",
        },
    }


def ops_suggestions(building_id: str | None = None) -> dict[str, Any]:
    ind = ops_indicators(building_id)
    x = ind["indicators"]
    ewi = x.get("ewi") or 0.0
    su = x.get("su") or 0.0
    dh = x.get("dh") or 1.0
    items: list[dict[str, Any]] = []
    if ewi >= 0.7:
        items.append(
            {
                "priority": "high",
                "title": "夜间基荷偏高，建议启用非工作时段自动关停策略",
                "expected_saving_kwh_per_hour": 2.3,
            }
        )
    if su <= 0.45:
        items.append(
            {"priority": "medium", "title": "空间利用率偏低，建议合并低占用工位并优化排班", "expected_effect": "提升空间利用率"}
        )
    if dh <= 0.75:
        items.append({"priority": "high", "title": "设备健康度下降，建议优先巡检高负荷空调/风机回路", "expected_effect": "降低故障风险"})
    if not items:
        items.append({"priority": "low", "title": "当前运行总体稳定，建议按周复核策略参数", "expected_effect": "保持节能表现"})
    return {"building_id": building_id, "indicators": x, "items": items}


def _forecast_naive(
    building_id: str | None,
    horizon_hours: int,
    s: pd.Series,
) -> dict[str, Any]:
    baseline = float(s.tail(min(24, len(s))).mean())
    start = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    labels = [(start + timedelta(hours=i)).strftime("%m-%d %H:%M") for i in range(horizon_hours)]
    values = [round(baseline * (1.0 + ((i % 24) - 12) * 0.004), 3) for i in range(horizon_hours)]
    return {
        "building_id": building_id,
        "model": "naive_moving_average",
        "horizon_hours": horizon_hours,
        "labels": labels,
        "values": values,
    }


def forecast_energy(building_id: str | None = None, horizon_hours: int = 24) -> dict[str, Any]:
    df = load_energy().copy()
    if building_id:
        df = df[df["building_id"] == building_id]
    if df.empty:
        return {"building_id": building_id, "horizon_hours": horizon_hours, "labels": [], "values": [], "model": "none"}

    df = df.sort_values("monitor_time").tail(1500).copy()
    df["y"] = pd.to_numeric(df["electricity_kwh"], errors="coerce")
    df["ds"] = pd.to_datetime(df["monitor_time"])
    train = df.dropna(subset=["y", "ds"])[["ds", "y"]]
    if len(train) < 48:
        return _forecast_naive(building_id, horizon_hours, train["y"] if len(train) else pd.Series([0.0]))

    try:
        import logging

        logging.getLogger("prophet").setLevel(logging.ERROR)
        logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
        from prophet import Prophet

        m = Prophet(daily_seasonality=True, weekly_seasonality=False, yearly_seasonality=False)
        m.fit(train)
        future = m.make_future_dataframe(periods=horizon_hours, freq="h", include_history=False)
        fc = m.predict(future)
        labels = fc["ds"].dt.strftime("%m-%d %H:%M").tolist()
        values = [round(float(x), 3) for x in fc["yhat"].tolist()]
        return {
            "building_id": building_id,
            "model": "prophet",
            "horizon_hours": horizon_hours,
            "labels": labels,
            "values": values,
        }
    except Exception as ex:
        out = _forecast_naive(building_id, horizon_hours, train["y"])
        out["model"] = "naive_fallback"
        out["prophet_error"] = str(ex)
        return out


def report_text(kind: str, building_id: str | None = None) -> str:
    """纯文本摘要（调试/日志）；正式导出见 v2_report_export。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    indicators = ops_indicators(building_id)["indicators"]
    suggests = ops_suggestions(building_id)["items"]
    lines = [
        f"{'运营优化' if kind == 'operations' else 'ESG专项'}报告",
        f"生成时间: {now}",
        f"建筑: {building_id or 'ALL'}",
        "",
        "核心指标:",
        f"- EWI: {indicators.get('ewi')}",
        f"- SU : {indicators.get('su')}",
        f"- DH : {indicators.get('dh')}",
        "",
        "优化建议:",
    ]
    for i, it in enumerate(suggests, start=1):
        lines.append(f"{i}. [{it.get('priority')}] {it.get('title')}")
    return "\n".join(lines)


def save_upload_temp(data: bytes, original_name: str | None) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = ""
    if original_name and "." in original_name:
        ext = "." + original_name.rsplit(".", 1)[-1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        ext = ".jpg"
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(data)
    return path


def _legend() -> list[dict[str, str]]:
    return [
        {"status": "high", "color": "red", "meaning": "高耗能/异常"},
        {"status": "warning", "color": "yellow", "meaning": "预警"},
        {"status": "normal", "color": "green", "meaning": "正常/节能"},
    ]
