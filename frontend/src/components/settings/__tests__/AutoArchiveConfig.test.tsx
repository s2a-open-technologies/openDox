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

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AutoArchiveConfig } from "@/components/settings/AutoArchiveConfig";
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

function renderWithAuthFetch(
  authFetch: ReturnType<typeof vi.fn>,
  readOnly = false
) {
  mockedUseAuth.mockReturnValue({
    user: null,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch,
    acceptDisclaimer: vi.fn(),
  });
  return render(<AutoArchiveConfig readOnly={readOnly} />);
}

const defaultSettings = {
  audio_download_enabled: true,
  auto_archive_enabled: false,
  auto_archive_days: 90,
};

describe("AutoArchiveConfig", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads and pre-fills the auto-archive settings from the API", async () => {
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse({ auto_archive_enabled: true, auto_archive_days: 30 })
    );
    renderWithAuthFetch(authFetch);

    await waitFor(() =>
      expect(screen.getByLabelText("Automatisch archivieren")).toHaveAttribute(
        "data-state",
        "checked"
      )
    );
    expect(
      (screen.getByLabelText("Frist in Tagen") as HTMLInputElement).value
    ).toBe("30");
  });

  it("saves an edited day threshold as JSON and shows a success toast", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(defaultSettings))
      .mockResolvedValueOnce(jsonResponse({}));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await waitFor(() =>
      expect((screen.getByLabelText("Frist in Tagen") as HTMLInputElement).value).toBe("90")
    );
    const days = screen.getByLabelText("Frist in Tagen") as HTMLInputElement;
    await user.clear(days);
    await user.type(days, "14");
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/audio-settings/");
    expect(options.method).toBe("PUT");
    const body = JSON.parse(options.body);
    expect(body.auto_archive_days).toBe(14);
    expect(body.auto_archive_enabled).toBe(false);
    expect(toast.success).toHaveBeenCalledWith("Auto-Archivierung gespeichert");
  });

  it("toggling the switch persists on save (not before)", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(defaultSettings))
      .mockResolvedValueOnce(jsonResponse({}));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await waitFor(() =>
      expect(screen.getByLabelText("Automatisch archivieren")).toBeEnabled()
    );
    await user.click(screen.getByLabelText("Automatisch archivieren"));
    expect(authFetch).toHaveBeenCalledTimes(1); // no PUT yet

    await user.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    const body = JSON.parse(authFetch.mock.calls[1][1].body);
    expect(body.auto_archive_enabled).toBe(true);
  });

  it("shows a destructive hint and blocks save for an out-of-range day input", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(defaultSettings))
      .mockResolvedValueOnce(jsonResponse({}));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await waitFor(() =>
      expect((screen.getByLabelText("Frist in Tagen") as HTMLInputElement).value).toBe("90")
    );
    const days = screen.getByLabelText("Frist in Tagen") as HTMLInputElement;
    await user.clear(days);
    await user.type(days, "5000");

    expect(
      screen.getByText(/zwischen 1 und 3650/i)
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Speichern" })).toBeDisabled();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("shows an error toast when saving fails", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(defaultSettings))
      .mockResolvedValueOnce(jsonResponse({}, false));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await waitFor(() =>
      expect((screen.getByLabelText("Frist in Tagen") as HTMLInputElement).value).toBe("90")
    );
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Speichern fehlgeschlagen")
    );
  });

  it("disables all controls when readOnly is set", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse(defaultSettings));
    renderWithAuthFetch(authFetch, true);

    await waitFor(() =>
      expect(screen.getByLabelText("Automatisch archivieren")).toBeDisabled()
    );
    expect(screen.getByLabelText("Frist in Tagen")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Speichern" })).toBeDisabled();
  });
});