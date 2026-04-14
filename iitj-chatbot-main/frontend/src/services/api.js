// src/services/api.js
// Centralized API calls to the FastAPI backend

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.detail || err.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  /** Send a chat message */
  chat: ({ message, session_id, language }) =>
    request('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id, language }),
    }),

  /** Get health status */
  health: () => request('/health'),

  /** Get knowledge base stats */
  stats: () => request('/index/stats'),

  /** Get suggested questions */
  suggestions: () => request('/suggestions'),
}
