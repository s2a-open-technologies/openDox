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
import TranscriptView from "@/components/TranscriptView";
import type { Recording } from "@/pages/Dashboard";
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

const SEGMENTS = [
  { source: "Пациент принимает 5 мг.", target: "Der Patient nimmt 50 mg.", paragraph: 0, missing_numbers: ["5"], extra_numbers: ["50"] },
  { source: "Аллергии нет.", target: "Keine Allergien.", paragraph: 0, missing_numbers: [], extra_numbers: [] },
];

function translated(overrides: Partial<Recording> = {}): Recording {
  return {
    id: "sess-ru",
    dbId: 7,
    title: "Diktat russisch",
    categoryId: 1,
    categoryName: "Standard",
    timestamp: "06.11.2026 10:00:00",
    content: "Пациент принимает 5 мг. Аллергии нет.",
    summarize: "Zusammenfassung",
    summaryEnabled: true,
    userid: "1",
    sourceLanguage: "ru",
    translationLanguage: "de",
    translation: "Der Patient nimmt 50 mg. Keine Allergien.",
    translationSegments: SEGMENTS,
    ...overrides,
  };
}

function renderView(transcript: Recording, authFetch = vi.fn().mockResolvedValue(jsonResponse({}))) {
  mockedUseAuth.mockReturnValue({ authFetch } as unknown as ReturnType<typeof useAuth>);
  const onSave = vi.fn().mockResolvedValue(undefined);
  render(
    <TranscriptView
      transcript={transcript}
      categories={[{ id: 1, name: "Standard" }]}
      onNewRecording={vi.fn()}
      onSave={onSave}
      onCategoryChange={vi.fn()}
    />
  );
  return { onSave, authFetch };
}

async function confirm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Bestätigen" }));
}

describe("TranscriptView with a translated dictation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the original, the sentence pairs and flags differing numbers", () => {
    renderView(translated());

    expect(screen.getByText("Transkript (Original: Russisch)")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Übersetzung" })).toHaveAttribute("data-state", "active");
    expect(screen.getByRole("tab", { name: "Zusammenfassung" })).toBeInTheDocument();
    expect(screen.getByLabelText("Übersetzter Satz 1")).toHaveValue("Der Patient nimmt 50 mg.");
    expect(screen.getByText("Пациент принимает 5 мг.")).toBeInTheDocument();
    expect(screen.getByText("1 Satz mit abweichenden Zahlen, bitte besonders prüfen.")).toBeInTheDocument();
    expect(screen.getByText("Fehlt in der Übersetzung: 5 · Nur in der Übersetzung: 50")).toBeInTheDocument();
    expect(screen.getByText(/mit meinem Diktat verglichen/)).toBeInTheDocument();
    // "Kein Medizinprodukt" stays in the transcript view.
    expect(screen.getByText(/Kein Medizinprodukt/)).toBeInTheDocument();
  });

  it("keeps sentences read-only until confirmed and saves edits as segments", async () => {
    const authFetch = vi.fn((url: string, options?: RequestInit) => {
      if (options?.method === "PUT") {
        return Promise.resolve(
          jsonResponse({
            translation: "Der Patient nimmt 5 mg. Keine Allergien.",
            translation_segments: [{ ...SEGMENTS[0], target: "Der Patient nimmt 5 mg.", missing_numbers: [], extra_numbers: [] }, SEGMENTS[1]],
          })
        );
      }
      return Promise.resolve(jsonResponse({}));
    });
    const user = userEvent.setup();
    const { onSave } = renderView(translated(), authFetch);

    const first = screen.getByLabelText("Übersetzter Satz 1");
    expect(first).toHaveAttribute("readonly");
    await confirm(user);
    await user.clear(first);
    await user.type(first, "Der Patient nimmt 5 mg.");
    await user.click(screen.getByRole("button", { name: /Speichern/ }));

    await waitFor(() => expect(onSave).toHaveBeenCalled());
    const put = authFetch.mock.calls.find(([, options]) => options?.method === "PUT");
    expect(put?.[0]).toBe("/api/v1/records/record/7");
    expect(JSON.parse(put?.[1]?.body as string)).toEqual({
      translation_segments: [{ index: 0, target: "Der Patient nimmt 5 mg." }],
    });
    expect(screen.queryByText(/abweichenden Zahlen/)).not.toBeInTheDocument();
  });

  it("without LLM summary the translation is the only result, no summary tab", () => {
    renderView(
      translated({
        summaryEnabled: false,
        summarize: "Der Patient nimmt 50 mg. Keine Allergien.",
      })
    );

    expect(screen.getByRole("tab", { name: "Übersetzung" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Zusammenfassung" })).not.toBeInTheDocument();
  });

  it("copies the translation, not the original", async () => {
    // userEvent.setup() installs its own clipboard stub, so replace it afterwards.
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    renderView(translated());

    await confirm(user);
    const panel = screen.getByRole("tabpanel");
    await user.click(within(panel).getByRole("button", { name: /Kopieren/ }));

    expect(writeText).toHaveBeenCalledWith("Der Patient nimmt 50 mg. Keine Allergien.");
  });
});
