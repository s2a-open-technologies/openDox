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
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MyRetention } from "@/components/settings/MyRetention";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

const mockedUseAuth = vi.mocked(useAuth);

function jsonResponse(body: unknown, ok = true) {
  return { ok, json: async () => body } as Response;
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
  return render(<MyRetention />);
}

const GLOBAL_90 = { personal_days: null, global_enabled: true, global_days: 90 };

describe("MyRetention", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the global limit and blocks a longer personal period", async () => {
    renderWithAuthFetch(vi.fn().mockResolvedValue(jsonResponse(GLOBAL_90)));

    expect(await screen.findByText(/spätestens nach 90 Tagen/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Eigene Aufnahmen löschen nach (Tagen)"), "120");

    expect(screen.getByText("Bitte eine ganze Zahl zwischen 1 und 90 eingeben.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Speichern" })).toBeDisabled();
  });

  it("saves a shorter period and clears it with an empty field", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(GLOBAL_90))
      .mockResolvedValueOnce(jsonResponse({ ...GLOBAL_90, personal_days: 30 }))
      .mockResolvedValueOnce(jsonResponse(GLOBAL_90));
    renderWithAuthFetch(authFetch);
    const input = await screen.findByLabelText("Eigene Aufnahmen löschen nach (Tagen)");

    await userEvent.type(input, "30");
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    expect(JSON.parse(authFetch.mock.calls[1][1].body)).toEqual({ personal_days: 30 });

    await userEvent.clear(input);
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(3));
    expect(JSON.parse(authFetch.mock.calls[2][1].body)).toEqual({ personal_days: null });
  });
});
