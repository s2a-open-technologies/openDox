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
import UpdateBanner from "@/components/UpdateBanner";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/contexts/AuthContext", () => ({ useAuth: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);

const INFO = {
  current: "0.12.0",
  latest: "0.13.0",
  update_available: true,
  release_url: "https://github.com/s2a-open-technologies/openDox/releases/tag/v0.13.0",
};

function setup(role: string, info: object = INFO) {
  const authFetch = vi.fn().mockResolvedValue({ ok: true, json: async () => info });
  mockedUseAuth.mockReturnValue({ user: { role }, authFetch } as never);
  render(<UpdateBanner />);
  return authFetch;
}

describe("UpdateBanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("shows version and release link to admins", async () => {
    setup("admin");

    expect(
      await screen.findByText(/openDox 0\.13\.0 ist verfügbar \(installiert: 0\.12\.0\)/),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Release ansehen/ })).toHaveAttribute(
      "href",
      INFO.release_url,
    );
  });

  it("does not even ask for normal users", () => {
    const authFetch = setup("user");

    expect(authFetch).not.toHaveBeenCalled();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("stays hidden without an update", async () => {
    const authFetch = setup("admin", { ...INFO, update_available: false });

    await waitFor(() => expect(authFetch).toHaveBeenCalled());
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("remembers the dismissal per version", async () => {
    setup("admin");
    await userEvent.click(await screen.findByRole("button", { name: "Hinweis schließen" }));

    expect(screen.queryByRole("status")).toBeNull();
    expect(localStorage.getItem("update_banner_dismissed")).toBe("0.13.0");
  });
});
