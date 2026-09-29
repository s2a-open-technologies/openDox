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
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ArchiveDayList from "@/components/ArchiveDayList";
import type { Recording } from "@/pages/Dashboard";

const recordings: Recording[] = [
  {
    id: "a1",
    title: "Frühe Aufnahme",
    categoryId: 1,
    categoryName: "Kardiologie",
    timestamp: "23.09.2026 08:00:00",
    content: "",
    summarize: "",
    userid: "1",
  },
  {
    id: "a2",
    title: "Späte Aufnahme",
    categoryId: 1,
    categoryName: "Kardiologie",
    timestamp: "23.09.2026 17:30:00",
    content: "",
    summarize: "",
    userid: "1",
  },
];

describe("ArchiveDayList", () => {
  // "Today" fixed to 2026-09-23 so the "Heute" label for 23.09.2026 is
  // deterministic. vi.setSystemTime() also rewrites new Date()'s clock
  // (unlike a Date.now() spy) while real timers keep userEvent working.
  const NOW = new Date(2026, 8, 23, 12, 0, 0);

  beforeEach(() => {
    vi.clearAllMocks();
    vi.setSystemTime(NOW);
  });

  it("shows the date-prompt empty state when no date is selected", () => {
    render(
      <ArchiveDayList
        recordings={recordings}
        selectedDate={null}
        onSelectRecording={vi.fn()}
        onBackToDates={vi.fn()}
      />
    );

    expect(screen.getByText("Archiv")).toBeInTheDocument();
    expect(screen.getByText(/Wählen Sie links ein Datum/)).toBeInTheDocument();
  });

  it("renders the selected day's recordings sorted by time descending", () => {
    render(
      <ArchiveDayList
        recordings={recordings}
        selectedDate="2026-09-23"
        onSelectRecording={vi.fn()}
        onBackToDates={vi.fn()}
      />
    );

    expect(screen.getByText("Heute")).toBeInTheDocument();
    expect(screen.getByText("2 Transkriptionen")).toBeInTheDocument();
    expect(screen.getByText("Späte Aufnahme")).toBeInTheDocument();
    expect(screen.getByText("Frühe Aufnahme")).toBeInTheDocument();
    expect(screen.getByText("17:30")).toBeInTheDocument();
  });

  it("opens a recording via onSelectRecording", async () => {
    const onSelectRecording = vi.fn();
    const user = userEvent.setup();
    render(
      <ArchiveDayList
        recordings={recordings}
        selectedDate="2026-09-23"
        onSelectRecording={onSelectRecording}
        onBackToDates={vi.fn()}
      />
    );

    await user.click(screen.getByText("Späte Aufnahme"));
    expect(onSelectRecording).toHaveBeenCalledWith(
      expect.objectContaining({ id: "a2" })
    );
  });

  it("unarchives and deletes via the row menu", async () => {
    const onUnarchiveRecording = vi.fn();
    const onDeleteRecording = vi.fn();
    const user = userEvent.setup();
    render(
      <ArchiveDayList
        recordings={recordings}
        selectedDate="2026-09-23"
        onSelectRecording={vi.fn()}
        onUnarchiveRecording={onUnarchiveRecording}
        onDeleteRecording={onDeleteRecording}
        onBackToDates={vi.fn()}
      />
    );

    const menuButtons = screen.getAllByRole("button").filter((btn) =>
      btn.querySelector("svg.lucide-ellipsis")
    );
    await user.click(menuButtons[0]);
    await user.click(await screen.findByText("Wiederherstellen"));
    expect(onUnarchiveRecording).toHaveBeenCalledWith("a2");

    await user.click(menuButtons[0]);
    await user.click(await screen.findByText("Löschen"));
    expect(onDeleteRecording).toHaveBeenCalledWith("a2");
  });

  it("calls onBackToDates via the header button", async () => {
    const onBackToDates = vi.fn();
    const user = userEvent.setup();
    render(
      <ArchiveDayList
        recordings={recordings}
        selectedDate="2026-09-23"
        onSelectRecording={vi.fn()}
        onBackToDates={onBackToDates}
      />
    );

    await user.click(screen.getByTitle("Zurück zur Datumsauswahl"));
    expect(onBackToDates).toHaveBeenCalledTimes(1);
  });

  it("falls back to the date prompt when the selected date has no recordings", () => {
    render(
      <ArchiveDayList
        recordings={recordings}
        selectedDate="2020-01-01"
        onSelectRecording={vi.fn()}
        onBackToDates={vi.fn()}
      />
    );

    expect(screen.getByText(/Wählen Sie links ein Datum/)).toBeInTheDocument();
  });
});