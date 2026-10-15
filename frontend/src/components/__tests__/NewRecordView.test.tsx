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
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import NewRecordView from "@/components/NewRecordView";

describe("NewRecordView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the placeholder text when no transcript is available yet", () => {
    render(
      <NewRecordView
        onStartRecording={vi.fn()}
        onStopRecording={vi.fn()}
        isRecording={false}
        transcript=""
      />
    );

    expect(screen.getByText("Neue Aufnahme")).toBeInTheDocument();
    expect(screen.getByText("Hier erscheint Ihr Transkript.")).toBeInTheDocument();
  });

  it("shows the transcript text once it is available", () => {
    render(
      <NewRecordView
        onStartRecording={vi.fn()}
        onStopRecording={vi.fn()}
        isRecording={false}
        transcript="Der Patient berichtet über Kopfschmerzen."
      />
    );

    expect(
      screen.getByText("Der Patient berichtet über Kopfschmerzen.")
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Hier erscheint Ihr Transkript.")
    ).not.toBeInTheDocument();
  });

  it("shows the idle state and calls onStartRecording when the mic button is clicked", async () => {
    const onStartRecording = vi.fn();
    const user = userEvent.setup();
    render(
      <NewRecordView
        onStartRecording={onStartRecording}
        onStopRecording={vi.fn()}
        isRecording={false}
        transcript=""
      />
    );

    expect(
      screen.getByText("Klicken Sie auf das Mikrofon, um zu starten.")
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button"));

    expect(onStartRecording).toHaveBeenCalledTimes(1);
  });

  it("shows the recording state and calls onStopRecording when clicked while recording", async () => {
    const onStopRecording = vi.fn();
    const user = userEvent.setup();
    render(
      <NewRecordView
        onStartRecording={vi.fn()}
        onStopRecording={onStopRecording}
        isRecording={true}
        transcript=""
      />
    );

    expect(
      screen.getByText("Aufnahme läuft... Klicken Sie zum Beenden.")
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button"));

    expect(onStopRecording).toHaveBeenCalledTimes(1);
  });
});
