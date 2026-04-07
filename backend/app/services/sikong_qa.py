"""
司空大模型 text2text 合并数据（sikong_sft_all.jsonl）检索与演示。
生成方式：仓库根目录 merge_sikong_sft.py（输出默认同级 sft_merged/sikong_sft_all.jsonl）
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import settings


@lru_cache(maxsize=1)
def _load_rows() -> tuple[dict[str, Any], ...]:
    path: Path = settings.sikong_jsonl
    if not path.is_file():
        return tuple()
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                inp = (obj.get("input") or "").strip()
                outp = (obj.get("output") or "").strip()
                if inp or outp:
                    rows.append({"input": inp, "output": outp})
            except json.JSONDecodeError:
                continue
    return tuple(rows)


def is_ready() -> bool:
    return bool(_load_rows())


def count_rows() -> int:
    return len(_load_rows())


def search_sikong(query: str, limit: int = 20) -> dict[str, Any]:
    """关键词在问句/答句中匹配（演示级，可换向量检索）。"""
    q = (query or "").strip()
    if not q:
        return {"ready": is_ready(), "count": 0, "path": str(settings.sikong_jsonl), "results": []}

    rows = _load_rows()
    if not rows:
        return {
            "ready": False,
            "count": 0,
            "path": str(settings.sikong_jsonl),
            "message": "未找到司空数据文件，请先运行 merge_sikong_sft.py 生成 sikong_sft_all.jsonl",
            "results": [],
        }

    terms = [t for t in re.split(r"\s+", q) if t]
    scored: list[tuple[int, dict[str, Any]]] = []

    for r in rows:
        text = (r["input"] + "\n" + r["output"]).lower()
        score = 0
        for t in terms:
            if t.lower() in text:
                score += 1
        if score > 0:
            scored.append((score, r))

    scored.sort(key=lambda x: (-x[0], len(x[1]["input"])))
    top = [dict(r) for _, r in scored[:limit]]

    return {
        "ready": True,
        "count": len(top),
        "total_indexed": len(rows),
        "path": str(settings.sikong_jsonl),
        "results": top,
    }


def rag_sikong_demo(query: str, limit: int = 5) -> dict[str, Any]:
    r = search_sikong(query, limit=limit)
    items = r.get("results") or []
    if not items:
        return {
            "query": query,
            "source": "司空大模型微调语料（text2text）",
            "answer": "未命中相关问答条，请换关键词或确认已生成 jsonl。",
            "citations": [],
        }

    lines = []
    cites = []
    for i, it in enumerate(items[:5], 1):
        qshort = it["input"][:120] + ("…" if len(it["input"]) > 120 else "")
        oshort = it["output"][:400] + ("…" if len(it["output"]) > 400 else "")
        lines.append(f"[{i}] 问：{qshort}\n    答：{oshort}")
        cites.append({"input": it["input"][:200], "output_preview": it["output"][:200]})

    answer = (
        "【司空领域知识 · 演示拼接】以下条目来自建筑类专业问答语料，可与规范 PDF 知识库联合使用：\n\n"
        + "\n\n".join(lines)
    )
    return {
        "query": query,
        "source": "司空大模型微调语料（text2text）",
        "answer": answer,
        "citations": cites,
    }
