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
import { AutoDeleteConfig } from "@/components/settings/AutoDeleteConfig";
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

function renderWithAuthFetch(authFetch: ReturnType<typeof vi.fn>, readOnly = false) {
  mockedUseAuth.mockReturnValue({
    user: null,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch,
    acceptDisclaimer: vi.fn(),
  });
  return render(<AutoDeleteConfig readOnly={readOnly} />);
}

describe("AutoDeleteConfig", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads the settings, warns, and saves only the auto-delete fields", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ auto_delete_enabled: false, auto_delete_days: 180 }))
      .mockResolvedValueOnce(jsonResponse({}));
    renderWithAuthFetch(authFetch);

    await waitFor(() => expect(screen.getByLabelText("Aufbewahrung höchstens (Tage)")).toHaveValue(180));
    expect(screen.getByText(/unwiederbringlich/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("switch"));
    await userEvent.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    expect(JSON.parse(authFetch.mock.calls[1][1].body)).toEqual({
      auto_delete_enabled: true,
      auto_delete_days: 180,
    });
  });

  it("is not editable in read-only mode", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse({}));
    renderWithAuthFetch(authFetch, true);

    await waitFor(() => expect(authFetch).toHaveBeenCalled());
    expect(screen.getByRole("switch")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Speichern" })).toBeDisabled();
  });
});
