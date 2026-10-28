/*
  openDox - Medical transcription platform
  Copyright (C) 2026  S2A Open Technologies gGmbH
  SPDX-FileCopyrightText: 2026 S2A Open Technologies gGmbH
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

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuditLog } from "@/components/settings/AuditLog";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

const mockedUseAuth = vi.mocked(useAuth);

const PAGE = {
  total: 2,
  items: [
    {
      id: 2,
      timestamp: "2026-10-28T10:00:00Z",
      actor_name: "admin1",
      actor_role: "admin",
      action: "settings.llm.update",
      outcome: "success",
      target_type: "settings",
      target_id: "llm",
      ip: "10.0.0.1",
      details: { fields: ["llm_api_key", "llm_model"] },
    },
    {
      id: 1,
      timestamp: "2026-10-28T09:00:00Z",
      actor_name: "dr.mueller",
      actor_role: null,
      action: "auth.login",
      outcome: "failure",
      target_type: null,
      target_id: null,
      ip: "10.0.0.2",
      details: { reason: "invalid_credentials" },
    },
  ],
};

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
  return render(<AuditLog />);
}

describe("AuditLog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders translated actions, outcomes and details", async () => {
    const authFetch = vi.fn().mockResolvedValue({ ok: true, json: async () => PAGE } as Response);

    renderWithAuthFetch(authFetch);

    expect(await screen.findByText("LLM-Einstellungen geändert")).toBeInTheDocument();
    expect(screen.getByText("Felder: llm_api_key, llm_model")).toBeInTheDocument();
    expect(screen.getByText("Falscher Benutzername oder falsches Passwort")).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Fehlgeschlagen")).toBeInTheDocument();
    expect(screen.getByText("1–2 von 2")).toBeInTheDocument();
  });

  it("sends the chosen filters as query parameters", async () => {
    const authFetch = vi.fn().mockResolvedValue({ ok: true, json: async () => PAGE } as Response);
    renderWithAuthFetch(authFetch);
    await screen.findByText("LLM-Einstellungen geändert");

    await userEvent.selectOptions(screen.getByLabelText("Bereich"), "auth");
    await userEvent.selectOptions(screen.getByLabelText("Ergebnis"), "denied");
    await userEvent.type(screen.getByLabelText("Benutzer"), "mueller");
    await userEvent.click(screen.getByRole("button", { name: "Filtern" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    const url = new URL(authFetch.mock.calls[1][0], "http://x");
    expect(url.pathname).toBe("/api/v1/settings/audit/");
    expect(url.searchParams.get("action")).toBe("auth.");
    expect(url.searchParams.get("outcome")).toBe("denied");
    expect(url.searchParams.get("actor")).toBe("mueller");
    expect(url.searchParams.get("offset")).toBe("0");
  });
});
