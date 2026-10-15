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
import { render, screen, waitFor } from "@testing-library/react";
import SystemSettings from "@/components/settings/SystemSettings";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

function jsonResponse(body: unknown) {
  return { json: async () => body } as Response;
}

function renderWithAuthFetch(authFetch: ReturnType<typeof vi.fn>) {
  mockedUseAuth.mockReturnValue({
    user: null,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch,
    acceptDisclaimer: vi.fn(),
  });
  return render(<SystemSettings />);
}

describe("SystemSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("fetches and displays the app version and service health statuses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ version: "1.2.3" }))
    );
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse({
        services: [
          { name: "Postgres", status: "online" },
          { name: "Redis", status: "offline" },
          { name: "S3", status: "disabled" },
        ],
      })
    );
    renderWithAuthFetch(authFetch);

    expect(await screen.findByText("v1.2.3")).toBeInTheDocument();
    expect(screen.getByText("Postgres")).toBeInTheDocument();
    expect(screen.getByText("Online")).toBeInTheDocument();
    expect(screen.getByText("Redis")).toBeInTheDocument();
    expect(screen.getByText("Nicht erreichbar")).toBeInTheDocument();
    expect(screen.getByText("S3")).toBeInTheDocument();
    expect(screen.getByText("Deaktiviert")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/Zuletzt geprüft:/)).toBeInTheDocument());
  });

  it("shows a checking placeholder before the first health check resolves", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ version: "1.0.0" })));
    const authFetch = vi.fn().mockReturnValue(new Promise(() => {})); // never resolves
    renderWithAuthFetch(authFetch);

    expect(screen.getByText("Prüfe...")).toBeInTheDocument();
    expect(screen.getByText("Prüfung...")).toBeInTheDocument();
  });

  it("does not show a version suffix when /api/version fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const authFetch = vi.fn().mockResolvedValue(jsonResponse({ services: [] }));
    renderWithAuthFetch(authFetch);

    await waitFor(() => expect(screen.getByText(/Zuletzt geprüft:/)).toBeInTheDocument());
    expect(screen.queryByText(/^v\d/)).not.toBeInTheDocument();
  });

  it("clears services and still records a check time when the health request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ version: "1.0.0" })));
    const authFetch = vi.fn().mockRejectedValue(new Error("down"));
    renderWithAuthFetch(authFetch);

    await waitFor(() => expect(screen.getByText(/Zuletzt geprüft:/)).toBeInTheDocument());
    expect(screen.getByText("Prüfung...")).toBeInTheDocument();
  });

  it("polls the health check again after 10 seconds", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ version: "1.0.0" })));
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse({ services: [{ name: "Postgres", status: "online" }] })
    );
    renderWithAuthFetch(authFetch);

    await vi.advanceTimersByTimeAsync(0); // flush the initial checkHealth() call
    expect(authFetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(10000);
    expect(authFetch).toHaveBeenCalledTimes(2);
  });
});
