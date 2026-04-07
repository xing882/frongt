# 建筑能源智能管理（赛题演示后端 + 联调前端）

## 仓库结构

| 目录 | 说明 |
|------|------|
| `backend/` | FastAPI 服务（默认端口 **8765**） |
| `frontend/` | **Vue 3 + Element Plus + ECharts** 正式 Web 前端（Vite，默认 **5173**） |
| `frontend_test/` | 简易静态页 + Node 反向代理（可选） |
| `docs/` | API 与架构文档 |

## 一键联调（推荐）

1. 安装后端依赖（在 `backend` 下已配置 `requirements.txt`），安装前端依赖：`cd frontend && pnpm install`。
2. 在 **`building_energy_system`** 根目录执行：

```bash
npm install
npm run dev
```

将同时启动：API（`http://127.0.0.1:8765`）与前端开发服务器（`http://127.0.0.1:5173`）。浏览器打开前端地址即可；接口与 Swagger 仍为 `http://127.0.0.1:8765/docs`。

**Windows**：也可双击或在 PowerShell 中运行 `scripts/dev.ps1`（会打开两个新窗口分别跑后端与前端）。

**仅启动单端**：后端见下方「命令」；前端：`cd frontend && pnpm dev`。

## 文档

| 文档 | 说明 |
|------|------|
| [docs/TECHNICAL.md](docs/TECHNICAL.md) | 架构、数据流、配置、部署与排错（含 V2 视觉实现要点） |
| [docs/API_FRONTEND.md](docs/API_FRONTEND.md) | **前端对接**：基址、CORS、全量 REST 接口与示例 |
| [docs/SPEC_V2_extracted.txt](docs/SPEC_V2_extracted.txt) | 赛题 V2.0 需求摘录（归档；**实现以代码与 OpenAPI 为准**） |
| [START.txt](START.txt) | 最短启动命令与端口说明 |

开发时以运行中的 **`/openapi.json`** 为权威契约；交互调试使用 **`/docs`**。

## V2.0 新增功能强化（MVP）

- 视觉识别占位接口：`POST /api/v2/vision/analyze`
- 图片上传（YOLOv8-seg 或 **YOLO-World**）：`POST /api/v2/vision/upload`（Query：`mode`、`prompt`、`conf` 可选），依赖见 `backend/requirements-v2-vision.txt`（YOLO-World 另需 CLIP；首次会下载权重）
- 数字孪生场景数据：`GET /api/v2/twin/scene`
- 运营优化建议：`GET /api/v2/ops/suggestions`
- 能耗预测：`GET /api/v2/forecast/energy`
- 运营/ESG 报告导出：`GET /api/v2/reports/{operations|esg}`

## MCP（严格 stdio）

在 `building_energy_system/backend` 下运行：

```bash
python -m app.mcp_server
```

该进程通过 stdin/stdout 与 MCP 客户端通信（不要在终端手动输入/回车）。
