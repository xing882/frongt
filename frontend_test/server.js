const express = require("express");
const http = require("http");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;
/** 与 uvicorn 端口一致；8000 在 Windows 上常被占用或触发 10013，建议 8765 */
const BACKEND = process.env.BACKEND_URL || "http://127.0.0.1:8765";

function shouldProxy(p) {
  return (
    p.startsWith("/api") ||
    p === "/health" ||
    p.startsWith("/docs") ||
    p.startsWith("/redoc") ||
    p === "/openapi.json"
  );
}

function proxyToBackend(req, res) {
  const u = new URL(BACKEND);
  const isHttps = u.protocol === "https:";
  const lib = isHttps ? require("https") : http;
  const port = u.port || (isHttps ? 443 : 80);

  const headers = { ...req.headers };
  headers.host = u.host;

  const opts = {
    hostname: u.hostname,
    port,
    path: req.originalUrl,
    method: req.method,
    headers,
  };

  const preq = lib.request(opts, (pres) => {
    res.writeHead(pres.statusCode || 502, pres.headers);
    pres.pipe(res);
  });

  preq.on("error", (err) => {
    res.status(502).type("json").send({
      error: "无法连接后端",
      backend: BACKEND,
      detail: err.message,
      hint: "在 backend 目录执行: python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8765",
    });
  });

  req.pipe(preq);
}

app.use((req, res, next) => {
  if (shouldProxy(req.path)) {
    return proxyToBackend(req, res);
  }
  next();
});

app.get("/favicon.ico", (req, res) => {
  res.status(204).end();
});

app.use(express.static(path.join(__dirname, "public")));

app.listen(PORT, () => {
  console.log(`测试页: http://127.0.0.1:${PORT}`);
  console.log(`反向代理 -> ${BACKEND}  （/api /health /docs 等）`);
});
