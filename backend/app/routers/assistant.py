from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services import kb_search, rag_answer, sikong_qa

router = APIRouter(prefix="/assistant", tags=["assistant"])


class UnifiedBody(BaseModel):
    query: str = Field(..., min_length=1)
    kb_pdf_limit: int = Field(8, ge=1, le=30)
    sikong_limit: int = Field(5, ge=1, le=20)


@router.post("/knowledge-merge")
def knowledge_merge(body: UnifiedBody) -> dict[str, Any]:
    """
    赛题智慧运维：合并「规范 PDF 知识库」+「司空 text2text 语料」检索结果，
    供 RAG / 大模型拼装上下文（演示）。
    """
    pdf = kb_search.search_kb(body.query, limit=body.kb_pdf_limit)
    sik = sikong_qa.search_sikong(body.query, limit=body.sikong_limit)
    return {
        "query": body.query,
        "sources": {
            "pdf_kb": {
                "ready": pdf.get("ready"),
                "count": pdf.get("count", 0),
                "items": pdf.get("results", []),
            },
            "sikong_qa": {
                "ready": sik.get("ready"),
                "count": sik.get("count", 0),
                "items": sik.get("results", []),
            },
        },
        "hint": "纯 RAG 场景请优先使用 POST /assistant/rag-answer；若需再接 LLM，可将本接口返回的 sources 作为 context。",
    }


class RagAnswerBody(BaseModel):
    """纯 RAG：规范 PDF + 司空语料检索后拼装回答（无生成式模型）。"""

    query: str = Field(..., min_length=1)
    kb_limit: int = Field(8, ge=1, le=30)
    sikong_limit: int = Field(5, ge=1, le=20)


@router.post("/rag-answer")
def rag_answer_endpoint(body: RagAnswerBody) -> dict[str, Any]:
    """
    基于 RAG：全文检索知识库与司空语料，将命中片段整理为结构化回答。
    适用于运维规范、设备与节能相关问答；能耗数值类问题请配合 /api/energy、/api/stats 使用。
    """
    return rag_answer.unified_rag_answer(
        body.query,
        kb_limit=body.kb_limit,
        sikong_limit=body.sikong_limit,
    )
