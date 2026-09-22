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
import { FailedTranscriptions } from "@/components/settings/FailedTranscriptions";
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
  return render(<FailedTranscriptions readOnly={readOnly} />);
}

describe("FailedTranscriptions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders failed tasks with title, error and a fallback title when title is missing", async () => {
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse([
        {
          task_id: 1,
          record_id: 10,
          title: "Aufnahme Kardio",
          error: "Whisper timeout",
          updated_at: "2024-05-01T10:00:00Z",
        },
        {
          task_id: 2,
          record_id: 20,
          title: "",
          error: null,
          updated_at: "2024-05-02T10:00:00Z",
        },
      ])
    );
    renderWithAuthFetch(authFetch);

    expect(await screen.findByText("Aufnahme Kardio")).toBeInTheDocument();
    expect(screen.getByText("Whisper timeout")).toBeInTheDocument();
    expect(screen.getByText("Aufnahme #20")).toBeInTheDocument();
    expect(screen.getByText("Unbekannter Fehler")).toBeInTheDocument();
  });

  it("shows the empty state when there are no failed tasks", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse([]));
    renderWithAuthFetch(authFetch);

    expect(
      await screen.findByText("Keine fehlgeschlagenen Transkriptionen")
    ).toBeInTheDocument();
  });

  it("retries a task, removes it from the list and shows a success toast", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse([
          {
            task_id: 3,
            record_id: 30,
            title: "Neuro Aufnahme",
            error: "Verbindungsfehler",
            updated_at: "2024-05-03T10:00:00Z",
          },
        ])
      )
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByText("Neuro Aufnahme");
    await user.click(screen.getByRole("button", { name: /Erneut versuchen/ }));

    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith("Transkription wird erneut versucht")
    );
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/records/tasks/3/retry");
    expect(options.method).toBe("POST");
    await waitFor(() =>
      expect(screen.queryByText("Neuro Aufnahme")).not.toBeInTheDocument()
    );
  });

  it("shows the server error detail when retry fails and keeps the task in the list", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse([
          {
            task_id: 4,
            record_id: 40,
            title: "Ortho Aufnahme",
            error: "Fehler",
            updated_at: "2024-05-04T10:00:00Z",
          },
        ])
      )
      .mockResolvedValueOnce(jsonResponse({ detail: "Datei nicht mehr vorhanden" }, false));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByText("Ortho Aufnahme");
    await user.click(screen.getByRole("button", { name: /Erneut versuchen/ }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Datei nicht mehr vorhanden")
    );
    expect(screen.getByText("Ortho Aufnahme")).toBeInTheDocument();
  });

  it("disables the retry button when readOnly is set", async () => {
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse([
        {
          task_id: 5,
          record_id: 50,
          title: "Gesperrt",
          error: "Fehler",
          updated_at: "2024-05-05T10:00:00Z",
        },
      ])
    );
    renderWithAuthFetch(authFetch, true);

    await screen.findByText("Gesperrt");
    expect(screen.getByRole("button", { name: /Erneut versuchen/ })).toBeDisabled();
  });
});
