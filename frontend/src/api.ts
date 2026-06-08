/**
 * API base path patch.
 * If VITE_ROOT_PATH is set (e.g. "/app"), all fetch calls to "/api/..." 
 * are automatically prefixed so they hit the backend under the sub-path.
 * Import this module BEFORE any code that calls fetch.
 */

const BASE_PATH = import.meta.env.VITE_ROOT_PATH || "";

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
