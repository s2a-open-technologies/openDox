/*
  openDox - Medical transcription platform
  Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
  SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
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

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";

function jsonResponse(body: unknown, ok = true) {
  return { ok, json: async () => body } as Response;
}

function renderAuth() {
  return renderHook(() => useAuth(), { wrapper: AuthProvider });
}

describe("AuthContext", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = "csrf_access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
  });

  it("throws when useAuth is used outside an AuthProvider", () => {
    expect(() => renderHook(() => useAuth())).toThrow(
      "useAuth must be used within an AuthProvider"
    );
  });

  it("starts unauthenticated with isLoading false when no token is stored", async () => {
    const { result } = renderAuth();

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("restores the session on mount when a token is already stored", async () => {
    localStorage.setItem("access_token", "existing-token");
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        id: 1,
        name: "dr.mueller",
        is_active: true,
        role: "user",
        disclaimer_accepted_at: null,
      })
    );

    const { result } = renderAuth();

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toMatchObject({ id: 1, name: "dr.mueller", role: "user" });

    const [url, options] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("/api/v1/auth/me");
    expect((options as RequestInit).method).toBe("GET");
  });

  it("logs in successfully, stores the token, and fetches the user", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ access_token: "new-token" }))
      .mockResolvedValueOnce(
        jsonResponse({
          id: 2,
          name: "admin1",
          is_active: true,
          role: "admin",
          disclaimer_accepted_at: "2026-01-01",
        })
      );

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    let success = false;
    await act(async () => {
      success = await result.current.login("admin1", "secret");
    });

    expect(success).toBe(true);
    expect(localStorage.getItem("access_token")).toBe("new-token");
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.name).toBe("admin1");

    const [loginUrl, loginOptions] = vi.mocked(fetch).mock.calls[0];
    expect(loginUrl).toBe("/api/v1/auth/login");
    expect(JSON.parse((loginOptions as RequestInit).body as string)).toEqual({
      name: "admin1",
      password: "secret",
    });
  });

  it("returns false and does not store a token when login fails", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ detail: "bad credentials" }, false)
    );

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    let success = true;
    await act(async () => {
      success = await result.current.login("admin1", "wrong");
    });

    expect(success).toBe(false);
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("returns false when the login response has no access_token", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}));

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    let success = true;
    await act(async () => {
      success = await result.current.login("admin1", "secret");
    });

    expect(success).toBe(false);
    expect(localStorage.getItem("access_token")).toBeNull();
  });

  it("clears local state and calls the logout endpoint on logout", async () => {
    localStorage.setItem("access_token", "token-1");
    localStorage.setItem("currentSession", "session-1");
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ ok: true }));

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.logout();
    });

    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("currentSession")).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();

    const lastCall = vi.mocked(fetch).mock.calls.at(-1)!;
    expect(lastCall[0]).toBe("/api/v1/auth/logout");
    expect((lastCall[1] as RequestInit).method).toBe("POST");
  });

  it("authFetch attaches the bearer token and CSRF header and includes credentials", async () => {
    localStorage.setItem("access_token", "my-token");
    document.cookie = "csrf_access_token=csrf-value";
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}));

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.authFetch("/api/v1/something", { method: "GET" });
    });

    const call = vi
      .mocked(fetch)
      .mock.calls.find(([url]) => url === "/api/v1/something");
    expect(call).toBeDefined();
    const options = call![1] as RequestInit;
    expect((options.headers as Record<string, string>).Authorization).toBe(
      "Bearer my-token"
    );
    expect((options.headers as Record<string, string>)["X-CSRF-TOKEN"]).toBe(
      "csrf-value"
    );
    expect(options.credentials).toBe("include");
  });

  it("authFetch sends an empty Authorization header when no token is stored", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}));

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.authFetch("/api/v1/something");
    });

    const [, options] = vi.mocked(fetch).mock.calls[0];
    expect((options as RequestInit).headers as Record<string, string>).toMatchObject({
      Authorization: "",
    });
  });

  it("acceptDisclaimer posts to the endpoint and updates the user on success", async () => {
    localStorage.setItem("access_token", "token-1");
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        jsonResponse({
          id: 1,
          name: "dr.mueller",
          is_active: true,
          role: "user",
          disclaimer_accepted_at: null,
        })
      )
      .mockResolvedValueOnce(jsonResponse({ disclaimer_accepted_at: "2026-09-22T00:00:00Z" }));

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user).not.toBeNull());

    let success = false;
    await act(async () => {
      success = await result.current.acceptDisclaimer();
    });

    expect(success).toBe(true);
    expect(result.current.user?.disclaimer_accepted_at).toBe("2026-09-22T00:00:00Z");

    const lastCall = vi.mocked(fetch).mock.calls.at(-1)!;
    expect(lastCall[0]).toBe("/api/v1/auth/accept-disclaimer");
    expect((lastCall[1] as RequestInit).method).toBe("POST");
  });

  it("acceptDisclaimer returns false when the request fails", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}, false));

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    let success = true;
    await act(async () => {
      success = await result.current.acceptDisclaimer();
    });

    expect(success).toBe(false);
  });
});
