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

  it("throws the server's message when the account is locked", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({
        detail: { code: "account_locked", message: "Account locked", params: {} },
      }),
    } as Response);

    const { result } = renderAuth();
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await expect(result.current.login("admin1", "secret")).rejects.toThrow(
        "Ihr Konto ist gesperrt"
      );
    });
    expect(localStorage.getItem("access_token")).toBeNull();
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

  describe("session renewal", () => {
    const statusResponse = (status: number, body: unknown = {}) =>
      ({ ok: status >= 200 && status < 300, status, json: async () => body }) as Response;

    const me = { id: 1, name: "dr.mueller", is_active: true, role: "user" };

    const fakeJwt = (expSeconds: number) =>
      `x.${btoa(JSON.stringify({ exp: expSeconds }))}.y`;

    it("renews the access token on 401 and retries the request once", async () => {
      localStorage.setItem("access_token", "old-access");
      localStorage.setItem("refresh_token", "old-refresh");
      vi.mocked(fetch).mockImplementation(async (input, init) => {
        const url = String(input);
        const auth = (init?.headers as Record<string, string> | undefined)?.Authorization;
        if (url.startsWith("/api/v1/auth/refresh")) {
          return statusResponse(200, { access_token: "new-access", refresh_token: "new-refresh" });
        }
        if (url === "/api/v1/auth/me") return statusResponse(200, me);
        return auth === "Bearer new-access" ? statusResponse(200, { ok: 1 }) : statusResponse(401);
      });

      const { result } = renderAuth();
      await waitFor(() => expect(result.current.isAuthenticated).toBe(true));

      let response: Response | undefined;
      await act(async () => {
        response = await result.current.authFetch("/api/v1/something");
      });

      expect(response?.status).toBe(200);
      expect(localStorage.getItem("access_token")).toBe("new-access");
      expect(localStorage.getItem("refresh_token")).toBe("new-refresh");
      const refreshCalls = vi
        .mocked(fetch)
        .mock.calls.filter(([url]) => String(url).startsWith("/api/v1/auth/refresh"));
      expect(refreshCalls).toHaveLength(1);
      expect(String(refreshCalls[0][0])).not.toContain("old-refresh");
      expect(JSON.parse((refreshCalls[0][1] as RequestInit).body as string)).toEqual({
        refresh_token: "old-refresh",
      });
    });

    it("shares one renewal between parallel 401s", async () => {
      localStorage.setItem("access_token", "old-access");
      localStorage.setItem("refresh_token", "old-refresh");
      vi.mocked(fetch).mockImplementation(async (input, init) => {
        const url = String(input);
        const auth = (init?.headers as Record<string, string> | undefined)?.Authorization;
        if (url.startsWith("/api/v1/auth/refresh")) {
          return statusResponse(200, { access_token: "new-access", refresh_token: "new-refresh" });
        }
        if (url === "/api/v1/auth/me") return statusResponse(200, me);
        return auth === "Bearer new-access" ? statusResponse(200) : statusResponse(401);
      });

      const { result } = renderAuth();
      await waitFor(() => expect(result.current.isAuthenticated).toBe(true));

      await act(async () => {
        await Promise.all([
          result.current.authFetch("/api/v1/a"),
          result.current.authFetch("/api/v1/b"),
        ]);
      });

      const refreshCalls = vi
        .mocked(fetch)
        .mock.calls.filter(([url]) => String(url).startsWith("/api/v1/auth/refresh"));
      expect(refreshCalls).toHaveLength(1);
    });

    it("ends the session when the server refuses the renewal", async () => {
      localStorage.setItem("access_token", "old-access");
      localStorage.setItem("refresh_token", "revoked");
      vi.mocked(fetch).mockImplementation(async (input) => {
        const url = String(input);
        if (url === "/api/v1/auth/me") return statusResponse(200, me);
        return statusResponse(401);
      });

      const { result } = renderAuth();
      await waitFor(() => expect(result.current.isAuthenticated).toBe(true));

      await act(async () => {
        await result.current.authFetch("/api/v1/something");
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(localStorage.getItem("access_token")).toBeNull();
      expect(localStorage.getItem("refresh_token")).toBeNull();
    });

    it("keeps the session when the server cannot be reached for the renewal", async () => {
      localStorage.setItem("access_token", "old-access");
      localStorage.setItem("refresh_token", "old-refresh");
      vi.mocked(fetch).mockImplementation(async (input) => {
        const url = String(input);
        if (url === "/api/v1/auth/me") return statusResponse(200, me);
        if (url.startsWith("/api/v1/auth/refresh")) throw new Error("offline");
        return statusResponse(401);
      });

      const { result } = renderAuth();
      await waitFor(() => expect(result.current.isAuthenticated).toBe(true));

      await act(async () => {
        await result.current.authFetch("/api/v1/something");
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(localStorage.getItem("refresh_token")).toBe("old-refresh");
    });

    it("restores an expired session on mount through the refresh token", async () => {
      localStorage.setItem("access_token", "expired");
      localStorage.setItem("refresh_token", "valid-refresh");
      vi.mocked(fetch).mockImplementation(async (input, init) => {
        const url = String(input);
        const auth = (init?.headers as Record<string, string> | undefined)?.Authorization;
        if (url.startsWith("/api/v1/auth/refresh")) {
          return statusResponse(200, { access_token: "fresh", refresh_token: "fresh-refresh" });
        }
        return auth === "Bearer fresh" ? statusResponse(200, me) : statusResponse(401);
      });

      const { result } = renderAuth();

      await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
      expect(result.current.user?.name).toBe("dr.mueller");
    });

    it("stores the refresh token on password login", async () => {
      vi.mocked(fetch)
        .mockResolvedValueOnce(statusResponse(200, { access_token: "a", refresh_token: "r" }))
        .mockResolvedValueOnce(statusResponse(200, me));

      const { result } = renderAuth();
      await waitFor(() => expect(result.current.isLoading).toBe(false));
      await act(async () => {
        await result.current.login("dr.mueller", "pw");
      });

      expect(localStorage.getItem("refresh_token")).toBe("r");
    });

    it("loginWithTokens (OIDC) stores both tokens and loads the user", async () => {
      vi.mocked(fetch).mockResolvedValue(statusResponse(200, me));

      const { result } = renderAuth();
      await waitFor(() => expect(result.current.isLoading).toBe(false));
      await act(async () => {
        await result.current.loginWithTokens("oidc-access", "oidc-refresh");
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(localStorage.getItem("access_token")).toBe("oidc-access");
      expect(localStorage.getItem("refresh_token")).toBe("oidc-refresh");
    });

    it("getFreshToken renews a token that is about to expire", async () => {
      const soon = fakeJwt(Math.floor(Date.now() / 1000) + 10);
      localStorage.setItem("access_token", soon);
      localStorage.setItem("refresh_token", "r");
      vi.mocked(fetch).mockImplementation(async (input) => {
        if (String(input).startsWith("/api/v1/auth/refresh")) {
          return statusResponse(200, { access_token: "renewed", refresh_token: "r2" });
        }
        return statusResponse(200, me);
      });

      const { result } = renderAuth();
      await waitFor(() => expect(result.current.isAuthenticated).toBe(true));

      let token = "";
      await act(async () => {
        token = await result.current.getFreshToken();
      });

      expect(token).toBe("renewed");
    });

    it("getFreshToken keeps a token that is still valid", async () => {
      const later = fakeJwt(Math.floor(Date.now() / 1000) + 3600);
      localStorage.setItem("access_token", later);
      vi.mocked(fetch).mockResolvedValue(statusResponse(200, me));

      const { result } = renderAuth();
      await waitFor(() => expect(result.current.isAuthenticated).toBe(true));

      let token = "";
      await act(async () => {
        token = await result.current.getFreshToken();
      });

      expect(token).toBe(later);
      expect(
        vi.mocked(fetch).mock.calls.some(([url]) => String(url).startsWith("/api/v1/auth/refresh"))
      ).toBe(false);
    });
  });
});
