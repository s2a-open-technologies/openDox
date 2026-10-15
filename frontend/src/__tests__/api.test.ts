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

import { describe, it, expect, vi, afterEach } from "vitest";
// src/test/setup.ts sets window.__ROOT_PATH__ = "" before importing "@/api"
// for the whole suite, so this top-level import reflects that no-root-path
// baseline (BASE_PATH === "" and window.fetch left unpatched).
import { BASE_PATH } from "@/api";

describe("api.ts BASE_PATH (default, no root path configured)", () => {
  it("resolves to an empty string when window.__ROOT_PATH__ is empty", () => {
    expect(BASE_PATH).toBe("");
  });
});

describe("api.ts fetch patching (isolated module re-imports)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
    delete (window as unknown as Record<string, unknown>).__ROOT_PATH__;
  });

  it("prepends the root path to fetch calls whose URL starts with /api/", async () => {
    vi.resetModules();
    const originalFetchMock = vi.fn().mockResolvedValue(new Response(null));
    vi.stubGlobal("fetch", originalFetchMock);
    (window as unknown as Record<string, unknown>).__ROOT_PATH__ = "/opendox";

    const mod = await import("@/api");

    expect(mod.BASE_PATH).toBe("/opendox");
    expect(window.fetch).not.toBe(originalFetchMock);

    await window.fetch("/api/v1/records");

    expect(originalFetchMock).toHaveBeenCalledTimes(1);
    expect(originalFetchMock).toHaveBeenCalledWith("/opendox/api/v1/records", undefined);
  });

  it("leaves URLs that do not start with /api/ untouched", async () => {
    vi.resetModules();
    const originalFetchMock = vi.fn().mockResolvedValue(new Response(null));
    vi.stubGlobal("fetch", originalFetchMock);
    (window as unknown as Record<string, unknown>).__ROOT_PATH__ = "/opendox";

    const mod = await import("@/api");

    expect(mod.BASE_PATH).toBe("/opendox");

    await window.fetch("/static/logo.png");

    expect(originalFetchMock).toHaveBeenCalledWith("/static/logo.png", undefined);
  });

  it("passes the init options through unchanged when prepending the root path", async () => {
    vi.resetModules();
    const originalFetchMock = vi.fn().mockResolvedValue(new Response(null));
    vi.stubGlobal("fetch", originalFetchMock);
    (window as unknown as Record<string, unknown>).__ROOT_PATH__ = "/opendox";

    await import("@/api");

    const init: RequestInit = { method: "POST", headers: { "X-Test": "1" } };
    await window.fetch("/api/v1/records", init);

    expect(originalFetchMock).toHaveBeenCalledWith("/opendox/api/v1/records", init);
  });

  it("does not patch window.fetch at all when no root path is configured", async () => {
    vi.resetModules();
    const originalFetchMock = vi.fn().mockResolvedValue(new Response(null));
    vi.stubGlobal("fetch", originalFetchMock);
    (window as unknown as Record<string, unknown>).__ROOT_PATH__ = "";

    const mod = await import("@/api");

    expect(mod.BASE_PATH).toBe("");
    expect(window.fetch).toBe(originalFetchMock);

    await window.fetch("/api/v1/records");
    expect(originalFetchMock).toHaveBeenCalledWith("/api/v1/records");
  });
});
