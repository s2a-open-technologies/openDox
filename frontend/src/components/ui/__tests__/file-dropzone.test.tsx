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
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { FileDropzone, matchesAccept } from "@/components/ui/file-dropzone";

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

function drop(target: HTMLElement, file: File) {
  fireEvent.dragOver(target, { dataTransfer: { files: [file] } });
  fireEvent.drop(target, { dataTransfer: { files: [file] } });
}

describe("FileDropzone", () => {
  beforeEach(() => vi.clearAllMocks());

  it("passes a clicked file to onFile", async () => {
    const onFile = vi.fn();
    render(<FileDropzone label="Datei wählen" accept=".txt" onFile={onFile} inputTestId="input" />);
    const file = new File(["a"], "liste.txt", { type: "text/plain" });

    await userEvent.upload(screen.getByTestId("input"), file);

    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("passes a dropped file to onFile", () => {
    const onFile = vi.fn();
    render(<FileDropzone label="Datei wählen" accept="audio/*" onFile={onFile} />);
    const file = new File(["a"], "diktat.mp3", { type: "audio/mpeg" });

    drop(screen.getByRole("button", { name: "Datei wählen" }), file);

    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("rejects a dropped file of the wrong type", () => {
    const onFile = vi.fn();
    render(<FileDropzone label="Datei wählen" accept=".pem,.crt" onFile={onFile} />);

    drop(screen.getByRole("button"), new File(["a"], "bild.png", { type: "image/png" }));

    expect(onFile).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalled();
  });

  it("ignores drops while disabled", () => {
    const onFile = vi.fn();
    render(<FileDropzone label="Datei wählen" onFile={onFile} disabled />);

    drop(screen.getByRole("button"), new File(["a"], "x.txt"));

    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByRole("button")).toHaveAttribute("aria-disabled", "true");
  });

  it("shows the selected file name", () => {
    render(
      <FileDropzone label="Datei wählen" onFile={vi.fn()} file={new File(["abc"], "backup.json")} />
    );

    expect(screen.getByText(/backup\.json/)).toBeInTheDocument();
  });
});

describe("matchesAccept", () => {
  it("matches extensions, wildcards and exact MIME types", () => {
    expect(matchesAccept(new File([""], "A.CSV"), ".csv")).toBe(true);
    expect(matchesAccept(new File([""], "a.wav", { type: "audio/wav" }), "audio/*")).toBe(true);
    expect(matchesAccept(new File([""], "a.json", { type: "application/json" }), "application/json")).toBe(true);
    expect(matchesAccept(new File([""], "a.png", { type: "image/png" }), ".pem,audio/*")).toBe(false);
    expect(matchesAccept(new File([""], "a.png"), undefined)).toBe(true);
  });
});
