# 建筑能源智能管理（赛题演示后端 + 联调前端）

## 文档

| 文档 | 说明 |
|------|------|
| [docs/TECHNICAL.md](docs/TECHNICAL.md) | 架构、数据流、配置、部署与排错（含 V2 视觉实现要点） |
| [docs/API_FRONTEND.md](docs/API_FRONTEND.md) | **前端对接**：基址、CORS、全量 REST 接口与示例 |
| [docs/SPEC_V2_extracted.txt](docs/SPEC_V2_extracted.txt) | 赛题 V2.0 需求摘录（归档；**实现以代码与 OpenAPI 为准**） |
| [START.txt](START.txt) | 最短启动命令与端口说明 |

开发时以运行中的 **`/openapi.json`** 为权威契约；交互调试使用 **`/docs`**。

## 前端使用说明

- 正式前端目录：`frontend`（Vue 3 + Vite）。
- 推荐启动：在 `frontend` 下执行 `npm install && npm run dev`。
- 兼容启动：在 `frontend_test` 下执行 `npm start`，会转发到 `../frontend` 的 `dev` 命令。
- 默认前端通过 Vite 代理访问后端 `http://127.0.0.1:8765`（见 `frontend/vite.config.js`）。

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
