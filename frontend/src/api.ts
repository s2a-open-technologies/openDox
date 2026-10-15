/*
  openDox - Medical transcription platform
  Copyright (C) 2025  S2A Open Technologies gGmbH
  SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
  SPDX-License-Identifier: AGPL-3.0-or-later

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU Affero General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU Affero General Public License for more details.

  You should have received a copy of the GNU Affero General Public License
  along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/

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