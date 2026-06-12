/**
 * API base path patch.
 *
 * Prepends the deployment root path (e.g. "/opendox") to all fetch calls
 * whose URLs start with "/api/". The root path is determined at runtime:
 *
 *   1. window.__ROOT_PATH__ — injected by the backend into index.html
 *   2. import.meta.env.VITE_ROOT_PATH — Vite build-time fallback (dev only)
 *
 * Import this module BEFORE any code that calls fetch.
 */

export const BASE_PATH: string =
  (window as unknown as Record<string, unknown>).__ROOT_PATH__ as string ||
  import.meta.env.VITE_ROOT_PATH ||
  "";

if (BASE_PATH) {
  const originalFetch = window.fetch;
  window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    let url = typeof input === "string" ? input : input.toString();
    if (url.startsWith("/api/")) {
      url = BASE_PATH + url;
    }
    return originalFetch(url, init);
  };
}