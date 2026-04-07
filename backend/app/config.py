import os
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_REPO = _BACKEND.parent
# 仓库根目录的上级（通常为「BDG数据集」工作区，与 building_energy_system 并列放 bdg_cleaned_output、sft_merged）
_WORKSPACE = _REPO.parent


def _path_file(env_key: str, *candidates: Path) -> Path:
    v = os.environ.get(env_key)
    if v:
        return Path(v)
    for p in candidates:
        if p.is_file():
            return p
    return candidates[0]


def _path_dir(env_key: str, *candidates: Path) -> Path:
    v = os.environ.get(env_key)
    if v:
        return Path(v)
    for p in candidates:
        if p.is_dir():
            return p
    return candidates[0]


class Settings:
    energy_csv: Path = _path_file(
        "ENERGY_CSV",
        _WORKSPACE / "bdg_cleaned_output" / "building_energy_hourly.csv",
        _REPO / "bdg_cleaned_output" / "building_energy_hourly.csv",
    )
    metadata_csv: Path = _path_file(
        "METADATA_CSV",
        _WORKSPACE / "bdg_cleaned_output" / "metadata_subset.csv",
        _REPO / "bdg_cleaned_output" / "metadata_subset.csv",
    )
    data_dictionary_csv: Path = _path_file(
        "DATA_DICTIONARY_CSV",
        _WORKSPACE / "bdg_cleaned_output" / "data_dictionary.csv",
        _REPO / "bdg_cleaned_output" / "data_dictionary.csv",
    )
    # 规范 PDF 目录：优先项目内 kb_documents，其次工作区根下同名或旧目录名
    kb_root: Path = _path_dir(
        "KB_ROOT",
        _REPO / "kb_documents",
        _WORKSPACE / "kb_documents",
        _WORKSPACE / "知识库所需文档",
        _REPO / "知识库所需文档",
    )
    kb_index_db: Path = _path_file("KB_INDEX_DB", _BACKEND / "data" / "kb_index.sqlite")
    # 司空合并语料 jsonl（merge_sikong_sft.py 生成）
    sikong_jsonl: Path = _path_file(
        "SIKONG_JSONL",
        _WORKSPACE / "sft_merged" / "sikong_sft_all.jsonl",
        _REPO / "sft_merged" / "sikong_sft_all.jsonl",
    )

    api_prefix: str = os.environ.get("API_PREFIX", "/api")
    cors_origins: list[str] = [
        x.strip()
        for x in os.environ.get(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,"
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:4173,http://127.0.0.1:4173",
        ).split(",")
        if x.strip()
    ]


settings = Settings()
