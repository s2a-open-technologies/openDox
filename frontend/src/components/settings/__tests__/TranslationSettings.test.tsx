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
import { TranslationSettings } from "@/components/settings/TranslationSettings";
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

const STORED = { enabled: false, access: "selected", languages: ["ru"], target_language: "de" };

describe("TranslationSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("names the instance language as target and never offers it as a source", async () => {
    mockedUseAuth.mockReturnValue({
      authFetch: vi.fn().mockResolvedValue(jsonResponse(STORED)),
    } as unknown as ReturnType<typeof useAuth>);
    render(<TranslationSettings />);

    expect(await screen.findByText("Zielsprache: Deutsch.")).toBeInTheDocument();
    expect(screen.getByText("Russisch")).toBeInTheDocument();
    expect(screen.queryByText("Deutsch", { selector: "label span" })).not.toBeInTheDocument();
  });

  it("saves switch, access and languages", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(STORED))
      .mockResolvedValueOnce(jsonResponse({ ...STORED, enabled: true, access: "all", languages: ["ru", "ar"] }));
    mockedUseAuth.mockReturnValue({ authFetch } as unknown as ReturnType<typeof useAuth>);
    const user = userEvent.setup();
    render(<TranslationSettings />);

    await screen.findByText("Russisch");
    await user.click(screen.getByLabelText("Übersetzung einschalten"));
    await user.click(screen.getByLabelText(/Alle Benutzer/));
    await user.click(screen.getByText("Arabisch"));
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/translation/");
    expect(JSON.parse((options as RequestInit).body as string)).toEqual({
      enabled: true,
      access: "all",
      languages: ["ru", "ar"],
    });
  });

  it("is read-only for demo viewers", async () => {
    mockedUseAuth.mockReturnValue({
      authFetch: vi.fn().mockResolvedValue(jsonResponse(STORED)),
    } as unknown as ReturnType<typeof useAuth>);
    render(<TranslationSettings readOnly />);

    await screen.findByText("Russisch");
    expect(screen.getByLabelText("Übersetzung einschalten")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Speichern" })).toBeDisabled();
  });
});
