# building-energy-esg-fm · 建筑能源智能管理

以设施全生命周期运维为核心，融入 ESG 环境 / 社会 / 治理三维度评估框架，叠加人文关怀与 RAG 智能问答等能力（演进中）。本仓库包含 **FastAPI 后端** 与 **Vue 3 + Element Plus + ECharts** 前端联调代码。

## 仓库结构

| 目录 | 说明 |
|------|------|
| `backend/` | FastAPI 服务（默认端口 **8765**） |
| `frontend/` | **Vue 3 + Vite** 正式 Web 前端（默认 **5173**） |
| `frontend_test/` | 简易静态页 + Node 反向代理（可选） |
| `docs/` | API 与架构文档 |

## 一键联调（推荐）

1. 安装后端依赖（`backend/requirements.txt`），前端：`cd frontend && pnpm install`。
2. 在 **`building_energy_system`** 根目录执行：

```bash
npm install
npm run dev
```

将同时启动：API（`http://127.0.0.1:8765`）与前端（`http://127.0.0.1:5173`）。Swagger：`http://127.0.0.1:8765/docs`。

**Windows**：也可运行 `scripts/dev.ps1`。

**仅启动单端**：后端：`cd backend && py -3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8765`；前端：`cd frontend && pnpm dev`。

### 仅前端（与远程开发习惯一致）

```sh
cd frontend
pnpm install
pnpm dev
pnpm build
pnpm lint
```

## 文档

| 文档 | 说明 |
|------|------|
| [docs/TECHNICAL.md](docs/TECHNICAL.md) | 架构、数据流、配置、部署与排错 |
| [docs/API_FRONTEND.md](docs/API_FRONTEND.md) | 前端对接：基址、REST 接口与示例 |
| [docs/SPEC_V2_extracted.txt](docs/SPEC_V2_extracted.txt) | 赛题 V2.0 需求摘录（归档） |
| [START.txt](START.txt) | 最短启动命令与端口说明 |

## V2.0 能力要点（MVP）

- `POST /api/v2/vision/analyze`、`POST /api/v2/vision/upload`
- `GET /api/v2/twin/scene`、`GET /api/v2/ops/suggestions`、`GET /api/v2/forecast/energy`
- `GET /api/v2/reports/{operations|esg}`

## MCP（stdio）

在 `backend` 目录：`python -m app.mcp_server`
