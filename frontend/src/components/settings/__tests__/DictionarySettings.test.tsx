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
import DictionarySettings from "@/components/settings/DictionarySettings";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
}));

const mockedUseAuth = vi.mocked(useAuth);

const LIST_URL = "/api/v1/settings/dictionaries/";

function jsonResponse(body: unknown, ok = true) {
  return { ok, json: async () => body } as Response;
}

const GLOBAL = { id: 1, name: "ICD", user_id: null, term_count: 3, category_ids: [5] };
const OWN = { id: 2, name: "Mein Test", user_id: 7, term_count: 1, category_ids: [] };

function renderSettings(
  scope: "global" | "personal",
  routes: Record<string, unknown> = {}
) {
  const authFetch = vi.fn((url: string, options?: RequestInit) => {
    const method = options?.method ?? "GET";
    const key = `${method} ${url}`;
    if (key in routes) return Promise.resolve(jsonResponse(routes[key]));
    if (key === `GET ${LIST_URL}`) return Promise.resolve(jsonResponse([GLOBAL, OWN]));
    return Promise.resolve(jsonResponse({}, false));
  });
  mockedUseAuth.mockReturnValue({
    user: { id: 7, name: "dr.mueller", is_active: true, authenticated: true, role: "user" },
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch,
    acceptDisclaimer: vi.fn(),
  });
  render(<DictionarySettings scope={scope} />);
  return authFetch;
}

describe("DictionarySettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists only the dictionaries of its scope", async () => {
    renderSettings("personal");

    expect(await screen.findByText("Mein Test")).toBeInTheDocument();
    expect(screen.queryByText("ICD")).not.toBeInTheDocument();
  });

  it("shows term count and category usage of global dictionaries", async () => {
    renderSettings("global");

    expect(await screen.findByText("ICD")).toBeInTheDocument();
    expect(screen.getByText("3 Begriffe · in 1 Kategorie")).toBeInTheDocument();
  });

  it("shows at most 200 terms and narrows them by search", async () => {
    const terms = Array.from({ length: 250 }, (_, i) => `Begriff ${i}`);
    renderSettings("global", {
      [`GET ${LIST_URL}1`]: { ...GLOBAL, term_count: 250, terms },
    });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "„ICD“ bearbeiten" }));

    expect(await screen.findByText("Begriff 199")).toBeInTheDocument();
    expect(screen.queryByText("Begriff 200")).not.toBeInTheDocument();
    expect(screen.getByText(/und 50 weitere/)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Begriffe durchsuchen"), "Begriff 249");
    expect(screen.getByText("Begriff 249")).toBeInTheDocument();
  });

  it("adds a term and saves the whole list via PUT", async () => {
    const authFetch = renderSettings("personal", {
      [`GET ${LIST_URL}2`]: { ...OWN, terms: ["Sertralin"] },
      [`PUT ${LIST_URL}2`]: { ...OWN, term_count: 2, terms: ["Sertralin", "Metformin"] },
    });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "„Mein Test“ bearbeiten" }));
    await user.type(await screen.findByLabelText("Neuer Begriff"), "Metformin");
    await user.click(screen.getByRole("button", { name: "Hinzufügen" }));
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() =>
      expect(authFetch).toHaveBeenCalledWith(`${LIST_URL}2`, expect.objectContaining({ method: "PUT" }))
    );
    const put = authFetch.mock.calls.find(([, options]) => options?.method === "PUT")!;
    expect(JSON.parse(put[1]!.body as string)).toEqual({
      name: "Mein Test",
      terms: ["Sertralin", "Metformin"],
    });
  });

  it("uploads a file with the chosen mode", async () => {
    const authFetch = renderSettings("personal", {
      [`GET ${LIST_URL}2`]: { ...OWN, terms: [] },
      [`POST ${LIST_URL}2/upload`]: { ...OWN, term_count: 2 },
    });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "„Mein Test“ bearbeiten" }));
    await user.click(await screen.findByRole("button", { name: "Ersetzen" }));
    await user.upload(
      screen.getByTestId("dictionary-upload"),
      new File(["Sertralin\nMetformin\n"], "liste.txt", { type: "text/plain" })
    );

    await waitFor(() =>
      expect(authFetch).toHaveBeenCalledWith(
        `${LIST_URL}2/upload`,
        expect.objectContaining({ method: "POST" })
      )
    );
    const call = authFetch.mock.calls.find(([url]) => url === `${LIST_URL}2/upload`)!;
    const form = call[1]!.body as FormData;
    expect(form.get("mode")).toBe("replace");
    expect((form.get("file") as File).name).toBe("liste.txt");
  });
});
