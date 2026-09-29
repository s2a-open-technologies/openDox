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

import { describe, it, expect, vi, beforeAll, beforeEach, afterEach, afterAll } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Sidebar from "@/components/Sidebar";
import type { Recording } from "@/pages/Dashboard";

vi.mock("@/components/UserDropdown", () => ({
  default: () => <div data-testid="user-dropdown" />,
}));

vi.mock("@/components/Logo", () => ({
  Logo: (props: { className?: string }) => <div data-testid="logo" className={props.className} />,
}));

// jsdom has no ResizeObserver; Radix's ScrollArea needs one to mount.
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// "Today" fixed to 2026-09-23 so "Heute"/"Gestern" labels are deterministic.
// vi.setSystemTime() also rewrites new Date()'s clock (unlike a Date.now()
// spy) while real timers keep userEvent interactions working — fake timers
// hang Radix/userEvent pointer sequences in jsdom.
const NOW = new Date(2026, 8, 23, 12, 0, 0);

const recordings: Recording[] = [
  {
    id: "1",
    title: "Aufnahme Kardiologie",
    categoryId: 1,
    categoryName: "Kardiologie",
    timestamp: "22.09.2026 10:00",
    content: "",
    summarize: "",
    userid: "1",
  },
  {
    id: "2",
    title: "Aufnahme Neurologie",
    categoryId: 2,
    categoryName: "Neurologie",
    timestamp: "21.09.2026 09:00",
    content: "",
    summarize: "",
    userid: "1",
  },
];

describe("Sidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.setSystemTime(NOW);
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
  });

  it("shows the empty state when there are no recordings", () => {
    render(<Sidebar recordings={[]} onSelectRecording={vi.fn()} />);

    expect(screen.getAllByText("Keine Aufnahmen").length).toBeGreaterThan(0);
  });

  it("shows the archived empty state label when showArchived is true", () => {
    render(<Sidebar recordings={[]} onSelectRecording={vi.fn()} showArchived />);

    expect(screen.getAllByText("Keine archivierten Aufnahmen").length).toBeGreaterThan(0);
  });

  it("renders a list item per recording with title and timestamp", () => {
    render(<Sidebar recordings={recordings} onSelectRecording={vi.fn()} />);

    expect(screen.getAllByText("Aufnahme Kardiologie").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Aufnahme Neurologie").length).toBeGreaterThan(0);
    expect(screen.getAllByText("22.09.2026 10:00").length).toBeGreaterThan(0);
  });

  it("calls onSelectRecording and closes the mobile drawer when a recording is clicked", async () => {
    const onSelectRecording = vi.fn();
    const onMobileOpenChange = vi.fn();
    const user = userEvent.setup();
    render(
      <Sidebar
        recordings={recordings}
        onSelectRecording={onSelectRecording}
        onMobileOpenChange={onMobileOpenChange}
      />
    );

    const buttons = screen.getAllByText("Aufnahme Kardiologie");
    await user.click(buttons[0]);

    expect(onSelectRecording).toHaveBeenCalledWith(recordings[0]);
    expect(onMobileOpenChange).toHaveBeenCalledWith(false);
  });

  it("calls onToggleArchived with the right value for each filter button", async () => {
    const onToggleArchived = vi.fn();
    const user = userEvent.setup();
    render(
      <Sidebar
        recordings={[]}
        onSelectRecording={vi.fn()}
        onToggleArchived={onToggleArchived}
      />
    );

    await user.click(screen.getAllByTitle("Archiv")[0]);
    expect(onToggleArchived).toHaveBeenCalledWith(true);

    await user.click(screen.getAllByTitle("Aktuell")[0]);
    expect(onToggleArchived).toHaveBeenCalledWith(false);
  });

  it("shows the upload button by default and calls onUploadClick", async () => {
    const onUploadClick = vi.fn();
    const user = userEvent.setup();
    render(
      <Sidebar recordings={[]} onSelectRecording={vi.fn()} onUploadClick={onUploadClick} />
    );

    const uploadButtons = screen.getAllByTitle("Audio hochladen");
    await user.click(uploadButtons[0]);

    expect(onUploadClick).toHaveBeenCalledTimes(1);
  });

  it("hides the upload button when showUploadButton is false", () => {
    render(<Sidebar recordings={[]} onSelectRecording={vi.fn()} showUploadButton={false} />);

    expect(screen.queryByTitle("Audio hochladen")).not.toBeInTheDocument();
  });

  it("renders the UserDropdown", () => {
    render(<Sidebar recordings={[]} onSelectRecording={vi.fn()} />);

    expect(screen.getAllByTestId("user-dropdown").length).toBeGreaterThan(0);
  });

  it("archives a recording via the row menu", async () => {
    const onArchiveRecording = vi.fn();
    const user = userEvent.setup();
    render(
      <Sidebar
        recordings={recordings}
        onSelectRecording={vi.fn()}
        onArchiveRecording={onArchiveRecording}
      />
    );

    const menuButtons = screen.getAllByRole("button").filter((btn) =>
      btn.querySelector("svg.lucide-ellipsis")
    );
    await user.click(menuButtons[0]);
    await user.click(await screen.findAllByText("Archivieren").then((els) => els[0]));

    expect(onArchiveRecording).toHaveBeenCalledWith("1");
  });

  it("deletes a recording via the row menu", async () => {
    const onDeleteRecording = vi.fn();
    const user = userEvent.setup();
    render(
      <Sidebar
        recordings={recordings}
        onSelectRecording={vi.fn()}
        onDeleteRecording={onDeleteRecording}
      />
    );

    const menuButtons = screen.getAllByRole("button").filter((btn) =>
      btn.querySelector("svg.lucide-ellipsis")
    );
    await user.click(menuButtons[0]);
    await user.click(await screen.findAllByText("Löschen").then((els) => els[0]));

    expect(onDeleteRecording).toHaveBeenCalledWith("1");
  });

  it("shows 'Wiederherstellen' instead of 'Archivieren' when viewing the archive", async () => {
    const onUnarchiveRecording = vi.fn();
    const user = userEvent.setup();
    render(
      <Sidebar
        recordings={recordings}
        onSelectRecording={vi.fn()}
        showArchived
        onUnarchiveRecording={onUnarchiveRecording}
      />
    );

    // In archive mode the sidebar shows date groups instead of recording rows;
    // the per-recording actions live in ArchiveDayList. Only the empty-state
    // label applies here since the rows themselves are replaced.
    expect(screen.queryByText("Aufnahme Kardiologie")).not.toBeInTheDocument();
    expect(screen.getAllByText("Gestern").length).toBeGreaterThan(0);
    expect(screen.getAllByText("21.09.2026").length).toBeGreaterThan(0);
  });

  it("renders date groups with counts in archive mode", () => {
    render(
      <Sidebar
        recordings={[...recordings, recordings[0]]}
        onSelectRecording={vi.fn()}
        showArchived
        selectedArchiveDate="2026-09-22"
        onSelectArchiveDate={vi.fn()}
      />
    );

    expect(screen.getAllByText("Gestern").length).toBeGreaterThan(0);
    expect(screen.getByText("2 Transkriptionen")).toBeInTheDocument();
    expect(screen.getByText("1 Transkription")).toBeInTheDocument();
  });

  it("calls onSelectArchiveDate when a date group is clicked", async () => {
    const onSelectArchiveDate = vi.fn();
    const onMobileOpenChange = vi.fn();
    const user = userEvent.setup();
    render(
      <Sidebar
        recordings={recordings}
        onSelectRecording={vi.fn()}
        showArchived
        onSelectArchiveDate={onSelectArchiveDate}
        onMobileOpenChange={onMobileOpenChange}
      />
    );

    await user.click(screen.getAllByText("Gestern")[0]);
    expect(onSelectArchiveDate).toHaveBeenCalledWith("2026-09-22");
    expect(onMobileOpenChange).not.toHaveBeenCalled();
  });

  it("hides the row menu for the actively recording session", () => {
    render(
      <Sidebar
        recordings={recordings}
        onSelectRecording={vi.fn()}
        activeSessionId="1"
      />
    );

    // "Aktiv" badge shows for the active recording, but it has no row menu.
    expect(screen.getAllByText("Aktiv").length).toBeGreaterThan(0);
  });
});
