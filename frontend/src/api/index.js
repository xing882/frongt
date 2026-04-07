import { http } from './client'

export function getHealth() {
  return http.get('/health').then((r) => r.data)
}

export function getBuildings() {
  return http.get('/api/energy/buildings').then((r) => r.data)
}

export function getEnergyRecords(params) {
  return http.get('/api/energy/records', { params }).then((r) => r.data)
}

export function getStatsPeriod(params) {
  return http.get('/api/stats/period', { params }).then((r) => r.data)
}

export function getStatsAnomalies(params) {
  return http.get('/api/stats/anomalies', { params }).then((r) => r.data)
}

export function getStatsCopProxy(params) {
  return http.get('/api/stats/cop-proxy', { params }).then((r) => r.data)
}

export function getStatsTimeseries(params) {
  return http.get('/api/stats/timeseries', { params }).then((r) => r.data)
}

export function getMetricsCatalog() {
  return http.get('/api/stats/metrics-catalog').then((r) => r.data)
}

export function getBenchmarkScoreboard(params) {
  return http.get('/api/stats/benchmark/scoreboard', { params }).then((r) => r.data)
}

export function getKbSearch(params) {
  return http.get('/api/kb/search', { params }).then((r) => r.data)
}

export function getKbStatus() {
  return http.get('/api/kb/status').then((r) => r.data)
}

export function postKbRagDemo(body) {
  return http.post('/api/kb/rag-demo', body).then((r) => r.data)
}

export function getSikongSearch(params) {
  return http.get('/api/sikong/search', { params }).then((r) => r.data)
}

export function getSikongStatus() {
  return http.get('/api/sikong/status').then((r) => r.data)
}

export function postSikongRagDemo(body) {
  return http.post('/api/sikong/rag-demo', body).then((r) => r.data)
}

export function postAssistantRagAnswer(body) {
  return http.post('/api/assistant/rag-answer', body).then((r) => r.data)
}

export function postAssistantKnowledgeMerge(body) {
  return http.post('/api/assistant/knowledge-merge', body).then((r) => r.data)
}

export function getIncidents(params) {
  return http.get('/api/incidents', { params }).then((r) => r.data)
}

export function getIncidentsSummary() {
  return http.get('/api/incidents/summary').then((r) => r.data)
}

export function postIncident(body) {
  return http.post('/api/incidents', body).then((r) => r.data)
}

export function patchIncident(id, body) {
  return http.patch(`/api/incidents/${id}`, body).then((r) => r.data)
}

export function getAdminStatus() {
  return http.get('/api/admin/status').then((r) => r.data)
}

export function postAdminReload() {
  return http.post('/api/admin/reload').then((r) => r.data)
}

export function postAdminKbReindex() {
  return http.post('/api/admin/kb/reindex').then((r) => r.data)
}

export function getMcpTools() {
  return http.get('/api/mcp/tools').then((r) => r.data)
}

export function getV2TwinScene() {
  return http.get('/api/v2/twin/scene').then((r) => r.data)
}

/** @param {{ building_id?: string }} [params] */
export function getV2OpsIndicators(params) {
  return http.get('/api/v2/ops/indicators', { params }).then((r) => r.data)
}

/** @param {{ building_id?: string }} [params] */
export function getV2OpsSuggestions(params) {
  return http.get('/api/v2/ops/suggestions', { params }).then((r) => r.data)
}

export function getV2ForecastEnergy(params) {
  return http.get('/api/v2/forecast/energy', { params }).then((r) => r.data)
}

export function getDataDictionary() {
  return http.get('/api/meta/data-dictionary').then((r) => r.data)
}

export function postV2VisionAnalyze(body) {
  return http.post('/api/v2/vision/analyze', body).then((r) => r.data)
}

/** @param {File} file @param {{ mode?: string, prompt?: string, conf?: number }} [params] */
export function postV2VisionUpload(file, params = {}) {
  const fd = new FormData()
  fd.append('file', file)
  return http
    .post('/api/v2/vision/upload', fd, {
      params: {
        mode: params.mode ?? 'yolo_world',
        ...(params.prompt != null && params.prompt !== '' ? { prompt: params.prompt } : {}),
        ...(params.conf != null && !Number.isNaN(Number(params.conf))
          ? { conf: Number(params.conf) }
          : {}),
      },
    })
    .then((r) => r.data)
}
