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

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BackupSettings from "@/components/settings/BackupSettings";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

const mockedUseAuth = vi.mocked(useAuth);

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
  return render(<BackupSettings readOnly={readOnly} />);
}

function selectFile(container: HTMLElement, file: File) {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [file] } });
  return input;
}

describe("BackupSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("exports the backup, triggers a download and shows a success toast", async () => {
    const createObjectURL = vi.fn(() => "blob:mock-url");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const authFetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'attachment; filename="opendox-backup-2024.json"' },
      blob: async () => new Blob(["{}"], { type: "application/json" }),
    } as unknown as Response);
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await user.click(screen.getByRole("button", { name: /Backup herunterladen/ }));

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Backup heruntergeladen"));
    expect(authFetch).toHaveBeenCalledWith("/api/v1/settings/backup/");
    expect(createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect((clickSpy.mock.instances[0] as HTMLAnchorElement).download).toBe(
      "opendox-backup-2024.json"
    );
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");
  });

  it("shows an error toast when the export response is not ok", async () => {
    const authFetch = vi.fn().mockResolvedValue({ ok: false } as Response);
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await user.click(screen.getByRole("button", { name: /Backup herunterladen/ }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Export fehlgeschlagen"));
  });

  it("shows the network error message when the export request rejects", async () => {
    const authFetch = vi.fn().mockRejectedValue(new Error("Netzwerk nicht erreichbar"));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await user.click(screen.getByRole("button", { name: /Backup herunterladen/ }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Netzwerk nicht erreichbar")
    );
  });

  it("keeps the import button disabled until a file is selected, then enables it", async () => {
    const authFetch = vi.fn();
    const { container } = renderWithAuthFetch(authFetch);

    expect(screen.getByRole("button", { name: /Backup einspielen/ })).toBeDisabled();

    const file = new File(['{"a":1}'], "backup.json", { type: "application/json" });
    selectFile(container, file);

    expect(await screen.findByText("backup.json")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Backup einspielen/ })).toBeEnabled();
  });

  it("imports the selected file and shows a success toast", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonRes({ restored: ["whisper", "llm"] }));
    const user = userEvent.setup();
    const { container } = renderWithAuthFetch(authFetch);

    const file = new File(['{"a":1}'], "backup.json", { type: "application/json" });
    selectFile(container, file);
    await screen.findByText("backup.json");

    await user.click(screen.getByRole("button", { name: /Backup einspielen/ }));

    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith("Wiederhergestellt: whisper, llm")
    );
    const [url, options] = authFetch.mock.calls[0];
    expect(url).toBe("/api/v1/settings/backup/restore/");
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);
    expect((options.body as FormData).get("file")).toBe(file);

    // Selected file gets cleared after a successful import
    await waitFor(() =>
      expect(screen.queryByText("backup.json")).not.toBeInTheDocument()
    );
  });

  it("shows the server error detail when the import fails", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonRes({ detail: "Ungültiges Format" }, false));
    const user = userEvent.setup();
    const { container } = renderWithAuthFetch(authFetch);

    const file = new File(['{"a":1}'], "backup.json", { type: "application/json" });
    selectFile(container, file);
    await screen.findByText("backup.json");

    await user.click(screen.getByRole("button", { name: /Backup einspielen/ }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Ungültiges Format"));
  });

  it("disables export/import controls when readOnly is set", async () => {
    const authFetch = vi.fn();
    const { container } = renderWithAuthFetch(authFetch, true);

    expect(screen.getByRole("button", { name: /Backup herunterladen/ })).toBeDisabled();
    expect(
      container.querySelector('input[type="file"]') as HTMLInputElement
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: /Datei auswählen/ })).toBeDisabled();
  });
});

function jsonRes(body: unknown, ok = true) {
  return { ok, json: async () => body } as Response;
}
