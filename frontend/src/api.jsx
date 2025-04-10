// src/config/api.js
const API_BASE = "http://127.0.0.1:8000/api";

const API = {
  BASE: API_BASE,
  knowledge: `${API_BASE}/knowledge/`,
  knowledgeDetail: (id) => `${API_BASE}/knowledge/${id}/`,
  knowledgeChunks: (id) => `${API_BASE}/knowledge/${id}/chunks/`,
  chunkDetail: (chunkId) => `${API_BASE}/knowledge/chunk/${chunkId}/`,
  enterpriseQuery: `${API_BASE}/query_enterprise/`
};

export default API;
