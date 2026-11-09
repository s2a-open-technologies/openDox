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

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ManualDownloads } from "@/components/settings/ManualDownloads";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

function mockAuth(body: unknown) {
  const authFetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body } as Response);
  mockedUseAuth.mockReturnValue({
    user: null,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch,
    acceptDisclaimer: vi.fn(),
  } as unknown as ReturnType<typeof useAuth>);
  return authFetch;
}

const base = "https://github.com/s2a-open-technologies/openDox/releases";

describe("ManualDownloads", () => {
  it("renders one download link per manual and the release page", async () => {
    const authFetch = mockAuth({
      version: "1.2.3",
      release_url: `${base}/tag/v1.2.3`,
      manuals: [
        { key: "benutzer", file: "openDox-Benutzerhandbuch-1.2.3.pdf", url: `${base}/download/v1.2.3/openDox-Benutzerhandbuch-1.2.3.pdf` },
        { key: "administration", file: "openDox-Administrationshandbuch-1.2.3.pdf", url: `${base}/download/v1.2.3/openDox-Administrationshandbuch-1.2.3.pdf` },
        { key: "installation", file: "openDox-Installationshandbuch-1.2.3.pdf", url: `${base}/download/v1.2.3/openDox-Installationshandbuch-1.2.3.pdf` },
      ],
    });

    render(<ManualDownloads />);

    const user = await screen.findByRole("link", { name: /Benutzerhandbuch/ });
    expect(user).toHaveAttribute("href", `${base}/download/v1.2.3/openDox-Benutzerhandbuch-1.2.3.pdf`);
    expect(screen.getByRole("link", { name: /Administrationshandbuch/ })).toHaveAttribute(
      "href", `${base}/download/v1.2.3/openDox-Administrationshandbuch-1.2.3.pdf`);
    expect(screen.getByRole("link", { name: /Installationshandbuch/ })).toHaveAttribute(
      "href", `${base}/download/v1.2.3/openDox-Installationshandbuch-1.2.3.pdf`);
    expect(screen.getByRole("link", { name: /Release-Seite/ })).toHaveAttribute("href", `${base}/tag/v1.2.3`);
    expect(authFetch).toHaveBeenCalledWith("/api/v1/settings/manuals/");
  });

  it("says so when the version has no manuals", async () => {
    mockAuth({ version: "unknown", release_url: "", manuals: [] });

    render(<ManualDownloads />);

    expect(await screen.findByText(/keine Handbücher/)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
