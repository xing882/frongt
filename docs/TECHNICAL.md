# 建筑能源智能管理系统 — 技术文档

本文档描述 `building_energy_system` 仓库的后端架构、数据流、配置与运维要点，供开发与答辩使用。面向前端的接口约定见同目录下的 [API_FRONTEND.md](./API_FRONTEND.md)。

---

## 1. 系统概览

| 组件 | 说明 |
|------|------|
| 后端 API | Python 3 + **FastAPI**，异步可选，默认同步路由 |
| 数据存储 | 能耗与元数据：**CSV**（pandas 读取）；知识库：**SQLite FTS5** |
| 司空语料 | **JSONL** 文件，启动时按需加载并关键词检索 |
| 测试前端 | Node **Express** 静态页 + 反向代理到后端（可选） |
| MCP | 同时提供：① `GET /api/mcp/tools` 的 HTTP 能力清单；② 严格 MCP **stdio server** 进程（`python -m app.mcp_server`） |

**能力边界（赛题 A08 对齐）**

- 多条件能耗查询、时段汇总、COP 相关演示指标、用电 z-score 异常检测、时序图表数据、CSV 导出。
- 新增指标中心与建筑对标：`/api/stats/metrics-catalog`、`/api/stats/benchmark/scoreboard`。
- 规范 PDF 全文检索（FTS5）、司空 text2text 语料检索、纯 RAG 拼装回答（无生成式 LLM）。
- 新增轻量运维工单闭环：`/api/incidents`（list/create/patch）。
- 不提供：用户登录鉴权、实时物联网遥测（本项目为离线数据演示）。

---

## 2. 目录结构

```
building_energy_system/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 应用、CORS、/api 发现、404 提示
│   │   ├── config.py            # 路径与环境变量
│   │   ├── routers/             # energy, stats, kb, meta, sikong, assistant, admin, incidents, mcp_manifest, v2
│   │   └── services/            # energy_store, stats_service, kb_search, sikong_qa, rag_answer, report_export, v2_service…
│   ├── scripts/
│   │   └── ingest_kb.py         # PDF → 切块 → SQLite FTS
│   ├── data/                    # kb_index.sqlite、上传临时图 uploads/
│   └── requirements.txt
├── frontend_test/               # 联调静态页 + server.js 代理
├── docs/                        # 本文档、API_FRONTEND.md、赛题摘录 SPEC_V2_extracted.txt
└── START.txt                    # 快速启动命令
```

工作区（`BDG数据集`）中与后端相关的常见并列目录：

- `bdg_cleaned_output/`：清洗后的 `building_energy_hourly.csv` 等。
- `sft_merged/sikong_sft_all.jsonl`：司空合并语料。

---

## 3. 架构与数据流

### 3.1 请求路径

- 业务接口统一前缀：**`/api`**（可通过环境变量 `API_PREFIX` 修改）。
- 根路径 **`GET /`**、**`GET /health`** 不带 `/api`，用于探活。
- **`GET /api`** 与 **`GET /api/`**：返回常用端点示例 JSON（接口发现）。

### 3.2 能耗数据流

1. `energy_store.load_energy()` 使用 **lru_cache** 读取 `ENERGY_CSV` 指向的 CSV。
2. `load_metadata()` 读取建筑元数据 CSV。
3. `stats_service` 在内存 DataFrame 上做筛选、聚合、z-score、时序对齐。

**时间字段**：查询参数中的 `time_from` / `time_to` 为**含端点**的比较，格式建议 `YYYY-MM-DD HH:MM:SS`（与 CSV 中 `monitor_time` 一致）。

### 3.3 知识库（PDF → FTS）

1. 将 PDF 放入 `KB_ROOT` 对应目录（见 `config.py` 候选路径）。
2. 在 `backend` 下执行：`python scripts/ingest_kb.py`。
3. 生成 `KB_INDEX_DB`（默认 `backend/data/kb_index.sqlite`），表 `kb_fts` 为 FTS5。
4. 扫描版 PDF 无文本层时可能产生空块，检索命中少属预期。

### 3.4 司空语料

- 文件：`SIKONG_JSONL`（默认指向工作区 `sft_merged/sikong_sft_all.jsonl`）。
- `sikong_qa._load_rows()` 缓存全量 jsonl；`search_sikong` 在 input/output 中计分排序：整句子串匹配加权，并对连续中文补充 2 字滑窗词以提升自然语言问句召回。

### 3.5 智慧运维问答（RAG + 可选 LLM）

- 实现位置：`services/rag_answer.py`、`services/ops_context.py`（数据字典检索、能耗/异常摘要）、`services/llm_openai_compat.py`（OpenAI 兼容 `chat/completions`）。
- 流程：`search_kb`（FTS）+ `search_sikong`（关键词）+ `search_data_dictionary`（关键词）→ 条件注入 `stats_service.period_summary` / `anomaly_analysis` 文本摘要；若设置 `LLM_API_BASE`，则调用轻量 LLM 归纳生成，否则仅拼装。

### 3.6 V2 视觉上传（YOLO / YOLO-World）

- 路由：`POST /api/v2/vision/upload`，文件写入 `backend/data/uploads/`（每次请求新 UUID 文件名）。
- 可选依赖：`backend/requirements-v2-vision.txt`（`ultralytics`）；YOLO-World 另需 OpenAI CLIP（`import clip`），见该文件说明。
- **实现要点**：全局缓存模型权重；每次 `set_classes` 后将 `model.predictor = None`，避免 ultralytics 复用 `Predictor`/`AutoBackend` 导致「仅第一次上传识别正常」。推理段使用线程锁，避免并发共用一个模型实例。

---

## 4. 配置与环境变量

| 变量 | 含义 |
|------|------|
| `ENERGY_CSV` | 小时能耗表路径 |
| `METADATA_CSV` | 建筑元数据路径 |
| `DATA_DICTIONARY_CSV` | 数据字典 CSV |
| `KB_ROOT` | 规范 PDF 根目录 |
| `KB_INDEX_DB` | SQLite 索引文件路径 |
| `SIKONG_JSONL` | 司空合并 jsonl |
| `API_PREFIX` | 默认 `/api` |
| `CORS_ORIGINS` | 逗号分隔，默认含 `localhost:3000` 与 `127.0.0.1:3000` |

清洗与合并脚本（仓库根目录）：

- `BDG_DATA_DIR` / `BDG_OUT_DIR`：`clean_bdg_for_competition.py`
- `SIKONG_SRC_DIR` / `SIKONG_OUT_DIR`：`merge_sikong_sft.py`

---

## 5. 部署与运行

### 5.1 后端

```bash
cd building_energy_system/backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
```

- 交互文档：`http://127.0.0.1:8765/docs`
- OpenAPI JSON：`http://127.0.0.1:8765/openapi.json`

Windows 若端口 **8765** 绑定失败（如 `WinError 10013`），可换 **18888** 等端口。

### 5.2 严格 MCP Server（stdio）

本项目已提供 **严格 MCP 协议**的 stdio server 进程（与 FastAPI 分开运行）。

```bash
cd building_energy_system/backend
pip install -r requirements.txt
python -m app.mcp_server
```

该进程会在 **stdin/stdout** 上与 MCP 客户端通信（例如桌面端/智能体框架）。工具包含能耗查询、统计分析、知识库检索与纯 RAG 问答，名称与 `GET /api/mcp/tools` 的能力清单一致/相近。

### 5.3 测试前端（代理）

```bash
cd building_energy_system/frontend_test
set BACKEND_URL=http://127.0.0.1:8765   # PowerShell: $env:BACKEND_URL=...
npm start
```

浏览器访问 `http://127.0.0.1:3000`，静态页请求 `/api/*` 由 Node 转发到 `BACKEND_URL`。

### 5.4 生产建议

- 关闭 `--reload`，使用 gunicorn/uvicorn workers（需评估 pandas 多进程内存）。
- 反向代理（Nginx）终止 TLS，设置 `CORS_ORIGINS` 为正式前端域名。
- 大 CSV 可考虑替换为数据库；知识库可升级为向量库，但需另做嵌入与运维。

---

## 6. 错误与调试

- **404**：JSON 形如 `{"detail":"Not Found","path":"...","hint":"..."}`，多为路径未带 `/api` 前缀或路由拼写错误。
- **502（联调页）**：Node 无法连接 `BACKEND_URL`，检查 uvicorn 是否监听、端口是否一致。
- **知识库无结果**：先查 `GET /api/kb/status`；执行 `ingest_kb.py`。
- **司空无结果**：查 `GET /api/sikong/status`；确认 `sikong_sft_all.jsonl` 路径与编码 UTF-8。
- **V2 连续换图无检测**：确认已安装与 `requirements-v2-vision.txt` 一致的依赖；后端应含「set_classes 后 predictor 置空」逻辑（见 3.6）；可尝试 Query `conf=0.05` 或 `mode=yolo_seg`。

---

## 7. 版本与扩展

- 应用描述与 `GET /api` 中的 `version` 字段随 `main.py` 维护。
- 扩展点：在 `routers/` 新增路由并在 `main.py` `include_router`；复杂逻辑放 `services/`。
- 若接入真实 LLM：建议保留 `POST /api/assistant/knowledge-merge` 返回的 `sources` 作为 context，或替换 `rag-answer` 内部拼装逻辑。

---

## 8. 相关文档

- [API_FRONTEND.md](./API_FRONTEND.md) — 前端对接与接口清单
- [SPEC_V2_extracted.txt](./SPEC_V2_extracted.txt) — 赛题 V2.0 需求摘录（归档）
- 仓库内 `START.txt` — 最短启动命令与环境说明
