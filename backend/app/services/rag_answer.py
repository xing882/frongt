"""
纯 RAG 问答：检索规范 PDF（FTS）+ 司空语料（关键词），仅依据检索结果拼装回答，不调用生成式 LLM。
适用于赛题「基于 RAG 技术」的运维知识类问题。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.services import kb_search, sikong_qa


def _clean_snip(text: str) -> str:
    t = re.sub(r"【|】", "", str(text or ""))
    return re.sub(r"\s+", " ", t).strip()


def unified_rag_answer(
    query: str,
    kb_limit: int = 8,
    sikong_limit: int = 5,
) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {
            "query": query,
            "mode": "rag_only",
            "answer": "查询内容为空。",
            "citations": [],
            "retrieval": {"pdf": {}, "sikong": {}},
        }

    pdf = kb_search.search_kb(q, limit=kb_limit)
    sik = sikong_qa.search_sikong(q, limit=sikong_limit)

    pdf_items = pdf.get("results") or []
    sik_items = sik.get("results") or []
    citations: list[dict[str, Any]] = []

    blocks: list[str] = []

    # 一、规范 PDF
    if not kb_search.is_index_ready():
        blocks.append(
            "【一、规范与标准条文】\n"
            "知识库未建立索引：请在 backend 目录执行 python scripts/ingest_kb.py 后重试。\n"
        )
    elif pdf_items:
        lines = ["【一、规范与标准条文】", "以下为检索到的条文片段（节选）："]
        for i, c in enumerate(pdf_items, 1):
            src = Path(c["source_path"]).name
            snip = _clean_snip(c.get("snippet", ""))
            lines.append(f"{i}. 《{src}》 {snip}")
            citations.append(
                {
                    "type": "pdf",
                    "source": c["source_path"],
                    "chunk_id": c.get("chunk_id"),
                }
            )
        blocks.append("\n".join(lines))
    else:
        blocks.append(
            "【一、规范与标准条文】\n"
            "未命中已索引 PDF。可尝试更换关键词或补充知识库 PDF 后重新索引。\n"
        )

    # 二、司空领域问答语料
    if sik.get("message") and not sik_items:
        blocks.append(
            "【二、领域问答参考（司空语料）】\n"
            f"{sik.get('message', '司空语料未就绪或路径无效。')}\n"
        )
    elif sik_items:
        lines = ["【二、领域问答参考（司空语料）】", "以下为与问题相关的问答条目（节选）："]
        for i, it in enumerate(sik_items, 1):
            iq = (it.get("input") or "").strip()
            oa = (it.get("output") or "").strip()
            iq_short = iq[:200] + ("…" if len(iq) > 200 else "")
            oa_short = oa[:500] + ("…" if len(oa) > 500 else "")
            lines.append(f"{i}. 问：{iq_short}\n   答：{oa_short}")
            citations.append({"type": "sikong", "input_preview": iq[:120], "output_preview": oa[:120]})
        blocks.append("\n".join(lines))
    else:
        blocks.append(
            "【二、领域问答参考（司空语料）】\n"
            "未命中相关条目。可尝试拆分关键词或确认已生成 sikong_sft_all.jsonl。\n"
        )

    answer = "\n\n".join(blocks).strip()

    if not pdf_items and not sik_items and kb_search.is_index_ready() and sik.get("ready"):
        answer = (
            "未在规范知识库与司空语料中检索到与问题直接相关的内容。\n"
            "建议：① 换用设备/标准编号/术语等更具体的关键词；② 确认 PDF 已入库并完成索引；③ 确认司空 jsonl 路径正确。\n\n"
            + answer
        )

    return {
        "query": q,
        "mode": "rag_only",
        "description": "检索增强问答：回答由检索片段拼装而成，非大模型自由生成。",
        "answer": answer,
        "citations": citations,
        "retrieval": {
            "pdf": {
                "ready": pdf.get("ready", kb_search.is_index_ready()),
                "count": len(pdf_items),
                "message": pdf.get("message"),
            },
            "sikong": {
                "ready": sik.get("ready"),
                "count": len(sik_items),
                "total_indexed": sik.get("total_indexed"),
                "message": sik.get("message"),
            },
        },
    }
