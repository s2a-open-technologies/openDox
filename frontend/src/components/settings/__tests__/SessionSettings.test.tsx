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

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SessionSettings } from "@/components/settings/SessionSettings";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";

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

function mockAuth(authFetch: ReturnType<typeof vi.fn>) {
  mockedUseAuth.mockReturnValue({ authFetch } as unknown as ReturnType<typeof useAuth>);
}

describe("SessionSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads and saves the idle timeout", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ idle_timeout_minutes: 30 }))
      .mockResolvedValueOnce(jsonResponse({ idle_timeout_minutes: 15 }));
    mockAuth(authFetch);
    const user = userEvent.setup();
    render(<SessionSettings />);

    const input = screen.getByLabelText(/Abmelden nach Inaktivität/);
    await waitFor(() => expect(input).toHaveValue(30));
    await user.clear(input);
    await user.type(input, "15");
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/session-config/");
    expect((options as RequestInit).method).toBe("PUT");
    expect(JSON.parse((options as RequestInit).body as string)).toEqual({
      idle_timeout_minutes: 15,
    });
  });

  it("is read-only for demo viewers", async () => {
    mockAuth(vi.fn().mockResolvedValue(jsonResponse({ idle_timeout_minutes: 30 })));
    render(<SessionSettings readOnly />);

    expect(screen.getByLabelText(/Abmelden nach Inaktivität/)).toBeDisabled();
    expect(screen.getByRole("button", { name: "Speichern" })).toBeDisabled();
  });
});
