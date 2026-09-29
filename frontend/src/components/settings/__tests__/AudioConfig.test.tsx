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
import { AudioConfig } from "@/components/settings/AudioConfig";
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
  return render(<AudioConfig readOnly={readOnly} />);
}

const defaultSettings = {
  audio_download_enabled: true,
  audio_bitrate: "64k",
  audio_sample_rate: 16000,
  audio_format: "mp3",
};

describe("AudioConfig", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads and pre-fills the audio settings from the API", async () => {
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse({
        audio_download_enabled: true,
        audio_bitrate: "128k",
        audio_sample_rate: 44100,
        audio_format: "ogg",
      })
    );
    renderWithAuthFetch(authFetch);

    await waitFor(() =>
      expect((screen.getByLabelText("Dateiformat") as HTMLSelectElement).value).toBe("ogg")
    );
    expect((screen.getByLabelText("Bitrate (Qualität/Größe)") as HTMLSelectElement).value).toBe(
      "128k"
    );
    expect((screen.getByLabelText("Sample-Rate (Hz)") as HTMLSelectElement).value).toBe("44100");
    expect(screen.getByLabelText("Audio speichern")).toHaveAttribute("data-state", "checked");
  });

  it("hides the bitrate select for formats without a bitrate (e.g. wav)", async () => {
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse({ ...defaultSettings, audio_format: "wav" })
    );
    renderWithAuthFetch(authFetch);

    await waitFor(() =>
      expect((screen.getByLabelText("Dateiformat") as HTMLSelectElement).value).toBe("wav")
    );
    expect(screen.queryByLabelText("Bitrate (Qualität/Größe)")).not.toBeInTheDocument();
  });

  it("saves the updated config and shows a success toast", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(defaultSettings))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await waitFor(() =>
      expect((screen.getByLabelText("Dateiformat") as HTMLSelectElement).value).toBe("mp3")
    );
    await user.selectOptions(screen.getByLabelText("Dateiformat"), "flac");
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/audio-settings/");
    expect(options.method).toBe("PUT");
    const body = JSON.parse(options.body);
    expect(body.audio_format).toBe("flac");
    expect(toast.success).toHaveBeenCalledWith("Audio-Einstellungen gespeichert");
  });

  it("shows an error toast when saving fails", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(defaultSettings))
      .mockResolvedValueOnce(jsonResponse({}, false));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await waitFor(() =>
      expect((screen.getByLabelText("Dateiformat") as HTMLSelectElement).value).toBe("mp3")
    );
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Speichern fehlgeschlagen"));
  });

  it("disables all controls when readOnly is set", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse(defaultSettings));
    renderWithAuthFetch(authFetch, true);

    await waitFor(() =>
      expect((screen.getByLabelText("Dateiformat") as HTMLSelectElement).value).toBe("mp3")
    );
    expect(screen.getByLabelText("Audio speichern")).toBeDisabled();
    expect(screen.getByLabelText("Dateiformat")).toBeDisabled();
    expect(screen.getByLabelText("Sample-Rate (Hz)")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Speichern" })).toBeDisabled();
  });
});
