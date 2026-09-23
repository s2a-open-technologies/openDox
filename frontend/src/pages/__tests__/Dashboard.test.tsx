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

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Dashboard from "@/pages/Dashboard";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

// Sidebar/Recorder/TranscriptView are heavy real components (audio capture,
// live WS, rich text editing) that aren't the concern of this page-level
// test - they're replaced with minimal stand-ins that expose the exact props
// Dashboard wires up, so we can drive Dashboard's own state machine.

type SidebarMockProps = {
  showArchived: boolean;
  onToggleArchived: (show: boolean) => void;
  onUploadClick: () => void;
  recordings: { id: string; title: string }[];
  onSelectRecording: (recording: { id: string; title: string }) => void;
  onDeleteRecording: (id: string) => void;
  onArchiveRecording: (id: string) => void;
  onUnarchiveRecording: (id: string) => void;
  selectedArchiveDate: string | null;
  onSelectArchiveDate: (dateKey: string | null) => void;
};

vi.mock("@/components/Sidebar", () => ({
  default: (props: SidebarMockProps) => (
    <div data-testid="sidebar">
      <button onClick={() => props.onToggleArchived(!props.showArchived)}>
        ToggleArchived-{props.showArchived ? "archived" : "library"}
      </button>
      <button onClick={() => props.onSelectArchiveDate("2026-09-23")}>PickDate</button>
      <span data-testid="archive-date">{props.selectedArchiveDate ?? "none"}</span>
      <button onClick={props.onUploadClick}>OpenUpload</button>
      {props.recordings.map((r) => (
        <div key={r.id}>
          <span>{r.title}</span>
          <button onClick={() => props.onSelectRecording(r)}>Select-{r.title}</button>
          <button onClick={() => props.onDeleteRecording(r.id)}>Delete-{r.title}</button>
          <button onClick={() => props.onArchiveRecording(r.id)}>Archive-{r.title}</button>
          <button onClick={() => props.onUnarchiveRecording(r.id)}>Unarchive-{r.title}</button>
        </div>
      ))}
    </div>
  ),
}));

type ArchiveDayListMockProps = {
  recordings: { id: string; title: string }[];
  selectedDate: string | null;
  onSelectRecording: (recording: { id: string; title: string }) => void;
  onUnarchiveRecording: (id: string) => void;
  onDeleteRecording: (id: string) => void;
  onBackToDates: () => void;
};

vi.mock("@/components/ArchiveDayList", () => ({
  default: (props: ArchiveDayListMockProps) => (
    <div data-testid="archive-day-list">
      <span data-testid="archive-day-date">{props.selectedDate ?? "none"}</span>
      {props.recordings.map((r) => (
        <div key={r.id}>
          <span>{r.title}</span>
          <button onClick={() => props.onSelectRecording(r)}>ArchiveSelect-{r.title}</button>
          <button onClick={() => props.onUnarchiveRecording(r.id)}>ArchiveUnarchive-{r.title}</button>
          <button onClick={() => props.onDeleteRecording(r.id)}>ArchiveDelete-{r.title}</button>
        </div>
      ))}
      <button onClick={props.onBackToDates}>BackToDates</button>
    </div>
  ),
}));

type RecorderMockProps = {
  categoryId: string | null;
  onRecordingStart: (data: { session_id: string; id: number; title: string }) => void;
  onFinalTranscription: (sessionId: string, taskId: string) => void;
};

vi.mock("@/components/Recorder", () => ({
  default: React.forwardRef((_props: RecorderMockProps, _ref: unknown) => (
    <div data-testid="recorder">
      <span data-testid="recorder-category-id">{_props.categoryId}</span>
      <button
        onClick={() =>
          _props.onRecordingStart({ session_id: "sess-1", id: 42, title: "Neue Aufnahme" })
        }
      >
        StartRec
      </button>
      <button onClick={() => _props.onFinalTranscription("sess-1", "task-1")}>
        FinishRec
      </button>
    </div>
  )),
}));

type TranscriptViewMockProps = {
  transcript: { id: string; title: string };
  categories: { id: number }[];
  onNewRecording: () => void;
  onSave: (id: string, content: string, summarize: string) => void;
  onCategoryChange: (id: string, categoryId: number | undefined) => void;
};

vi.mock("@/components/TranscriptView", () => ({
  default: (props: TranscriptViewMockProps) => (
    <div data-testid="transcript-view">
      <span>TranscriptView-{props.transcript.title}</span>
      <button onClick={props.onNewRecording}>NewRecording</button>
      <button onClick={() => props.onSave(props.transcript.id, "edited content", "edited summary")}>
        SaveRec
      </button>
      <button
        onClick={() => props.onCategoryChange(props.transcript.id, props.categories[0]?.id)}
      >
        ChangeCategory
      </button>
    </div>
  ),
}));

const mockedUseAuth = vi.mocked(useAuth);

function jsonResponse(body: unknown, ok = true) {
  return { ok, json: async () => body } as Response;
}

const baseUser = {
  id: 5,
  name: "dr.mueller",
  is_active: true,
  authenticated: true,
  role: "user" as const,
  disclaimer_accepted_at: "2024-01-01",
};

type FetchMap = {
  records?: Record<string, unknown>[];
  categories?: { id: number; name: string }[];
  activeSession?: { active: boolean; session_id?: string };
};

function buildAuthFetch(overrides: FetchMap = {}) {
  const records = overrides.records ?? [];
  const categories = overrides.categories ?? [];
  const activeSession = overrides.activeSession ?? { active: false };

  return vi.fn((url: string, _options?: RequestInit) => {
    if (url.includes("/records/list-records/")) {
      return Promise.resolve(jsonResponse(records));
    }
    if (url.includes("/settings/categories/")) {
      return Promise.resolve(jsonResponse(categories));
    }
    if (url.includes("/records/active-session/")) {
      return Promise.resolve(jsonResponse(activeSession));
    }
    return Promise.resolve(jsonResponse({}));
  });
}

function renderDashboard(authFetch: ReturnType<typeof vi.fn>) {
  mockedUseAuth.mockReturnValue({
    user: baseUser,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch,
    acceptDisclaimer: vi.fn(),
  });
  return render(<Dashboard />);
}

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches and renders the recordings list for the current user", async () => {
    const authFetch = buildAuthFetch({
      records: [
        {
          id: 1,
          session_id: "s1",
          title: "Anamnese Müller",
          category_id: 2,
          timestamp: "2024-01-01",
          content: "",
          summarize: "",
          user_id: 5,
          task_id: null,
          has_audio: false,
        },
      ],
    });
    renderDashboard(authFetch);

    expect(await screen.findByText("Anamnese Müller")).toBeInTheDocument();
    expect(authFetch).toHaveBeenCalledWith("/api/v1/records/list-records/5?archived=false");
  });

  it("shows the welcome screen when there are no recordings", async () => {
    const authFetch = buildAuthFetch();
    renderDashboard(authFetch);

    expect(await screen.findByText("Willkommen bei openDox")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Neue Aufnahme starten" })
    ).toBeInTheDocument();
  });

  it("does not crash and keeps the list empty when the records fetch fails", async () => {
    const authFetch = vi.fn((url: string) => {
      if (url.includes("/records/list-records/")) {
        return Promise.resolve(jsonResponse(null, false));
      }
      if (url.includes("/settings/categories/")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.includes("/records/active-session/")) {
        return Promise.resolve(jsonResponse({ active: false }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    renderDashboard(authFetch);

    expect(await screen.findByText("Willkommen bei openDox")).toBeInTheDocument();
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
  });

  it("shows the retained unfinished-session banner when the server reports an active session", async () => {
    const authFetch = buildAuthFetch({
      activeSession: { active: true, session_id: "unfinished-1" },
    });
    renderDashboard(authFetch);

    expect(await screen.findByText("Unfertige Aufnahme")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fortsetzen" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Verwerfen" })).toBeInTheDocument();
  });

  it("pre-selects the 'Allgemein' category and passes it into the recorder on session start", async () => {
    const authFetch = buildAuthFetch({
      categories: [
        { id: 1, name: "Sonstiges" },
        { id: 2, name: "Allgemein" },
      ],
    });
    const user = userEvent.setup();
    renderDashboard(authFetch);

    await screen.findByText("Willkommen bei openDox");
    await user.click(screen.getByRole("button", { name: "Neue Aufnahme starten" }));
    const startButton = await screen.findByRole("button", { name: "Aufnahme starten" });
    expect(startButton).toBeEnabled();
    await user.click(startButton);

    await waitFor(() => expect(screen.getByTestId("recorder")).toBeInTheDocument());
    expect(screen.getByTestId("recorder-category-id")).toHaveTextContent("2");
  });

  it("disables the start button and shows a hint when no categories exist", async () => {
    const authFetch = buildAuthFetch({ categories: [] });
    const user = userEvent.setup();
    renderDashboard(authFetch);

    await screen.findByText("Willkommen bei openDox");
    await user.click(screen.getByRole("button", { name: "Neue Aufnahme starten" }));

    expect(
      await screen.findByText("Legen Sie zuerst eine Kategorie unter Einstellungen an.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aufnahme starten" })).toBeDisabled();
  });

  it("toggles between library and archive view, refetching with the archived flag", async () => {
    const authFetch = buildAuthFetch();
    const user = userEvent.setup();
    renderDashboard(authFetch);

    await screen.findByTestId("sidebar");
    await user.click(screen.getByRole("button", { name: /ToggleArchived/ }));

    await waitFor(() =>
      expect(authFetch).toHaveBeenCalledWith("/api/v1/records/list-records/5?archived=true")
    );
  });

  it("deletes a recording after confirmation and refetches the list", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    const authFetch = vi.fn((url: string, options?: RequestInit) => {
      if (url.includes("/records/list-records/")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: 1,
              session_id: "s1",
              title: "Zu löschende Aufnahme",
              category_id: null,
              timestamp: "2024-01-01",
              content: "",
              summarize: "",
              user_id: 5,
            },
          ])
        );
      }
      if (url.includes("/settings/categories/")) return Promise.resolve(jsonResponse([]));
      if (url.includes("/records/active-session/")) return Promise.resolve(jsonResponse({ active: false }));
      if (url.includes("/records/record/1") && options?.method === "DELETE") {
        return Promise.resolve(jsonResponse({ ok: true }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    const user = userEvent.setup();
    renderDashboard(authFetch);

    await screen.findByText("Zu löschende Aufnahme");
    await user.click(screen.getByRole("button", { name: "Delete-Zu löschende Aufnahme" }));

    await waitFor(() =>
      expect(authFetch).toHaveBeenCalledWith("/api/v1/records/record/1", { method: "DELETE" })
    );
    expect(toast.success).toHaveBeenCalledWith("Aufnahme gelöscht");
  });

  it("does not call the delete endpoint when the confirmation is cancelled", async () => {
    vi.stubGlobal("confirm", vi.fn(() => false));
    const authFetch = buildAuthFetch({
      records: [
        {
          id: 1,
          session_id: "s1",
          title: "Bleibt erhalten",
          category_id: null,
          timestamp: "2024-01-01",
          content: "",
          summarize: "",
          user_id: 5,
        },
      ],
    });
    const user = userEvent.setup();
    renderDashboard(authFetch);

    await screen.findByText("Bleibt erhalten");
    const callsBefore = authFetch.mock.calls.length;
    await user.click(screen.getByRole("button", { name: "Delete-Bleibt erhalten" }));

    expect(authFetch.mock.calls.length).toBe(callsBefore);
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("archives a recording and shows a success toast", async () => {
    const authFetch = vi.fn((url: string, options?: RequestInit) => {
      if (url.includes("/records/list-records/")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: 7,
              session_id: "s7",
              title: "Archivierbare Aufnahme",
              category_id: null,
              timestamp: "2024-01-01",
              content: "",
              summarize: "",
              user_id: 5,
            },
          ])
        );
      }
      if (url.includes("/settings/categories/")) return Promise.resolve(jsonResponse([]));
      if (url.includes("/records/active-session/")) return Promise.resolve(jsonResponse({ active: false }));
      if (url.includes("/records/record/7/archive") && options?.method === "PUT") {
        return Promise.resolve(jsonResponse({ ok: true }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    const user = userEvent.setup();
    renderDashboard(authFetch);

    await screen.findByText("Archivierbare Aufnahme");
    await user.click(screen.getByRole("button", { name: "Archive-Archivierbare Aufnahme" }));

    await waitFor(() =>
      expect(authFetch).toHaveBeenCalledWith("/api/v1/records/record/7/archive", { method: "PUT" })
    );
    expect(toast.success).toHaveBeenCalledWith("Aufnahme archiviert");
  });

  it("selects a recording, fetches its full detail and renders the transcript view", async () => {
    const authFetch = vi.fn((url: string) => {
      if (url.includes("/records/list-records/")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: 3,
              session_id: "s3",
              title: "Fertige Aufnahme",
              category_id: 9,
              timestamp: "2024-01-01",
              content: "hallo",
              summarize: "kurzfassung",
              user_id: 5,
            },
          ])
        );
      }
      if (url.includes("/settings/categories/")) {
        return Promise.resolve(jsonResponse([{ id: 9, name: "Kardiologie" }]));
      }
      if (url.includes("/records/active-session/")) return Promise.resolve(jsonResponse({ active: false }));
      if (url === "/api/v1/records/record/3") {
        return Promise.resolve(
          jsonResponse({
            id: 3,
            session_id: "s3",
            title: "Fertige Aufnahme",
            category_id: 9,
            timestamp: "2024-01-01",
            content: "hallo",
            summarize: "kurzfassung",
            user_id: 5,
          })
        );
      }
      return Promise.resolve(jsonResponse({}));
    });
    const user = userEvent.setup();
    renderDashboard(authFetch);

    await screen.findByText("Fertige Aufnahme");
    await user.click(screen.getByRole("button", { name: "Select-Fertige Aufnahme" }));

    expect(await screen.findByText("TranscriptView-Fertige Aufnahme")).toBeInTheDocument();
  });

  it("saves edits from the transcript view via a PUT request", async () => {
    const authFetch = vi.fn((url: string, options?: RequestInit) => {
      if (url.includes("/records/list-records/")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: 4,
              session_id: "s4",
              title: "Bearbeitbare Aufnahme",
              category_id: null,
              timestamp: "2024-01-01",
              content: "alt",
              summarize: "alt",
              user_id: 5,
            },
          ])
        );
      }
      if (url.includes("/settings/categories/")) return Promise.resolve(jsonResponse([]));
      if (url.includes("/records/active-session/")) return Promise.resolve(jsonResponse({ active: false }));
      if (url === "/api/v1/records/record/4" && options?.method === "PUT") {
        return Promise.resolve(jsonResponse({ ok: true }));
      }
      if (url === "/api/v1/records/record/4") {
        return Promise.resolve(
          jsonResponse({
            id: 4,
            session_id: "s4",
            title: "Bearbeitbare Aufnahme",
            category_id: null,
            timestamp: "2024-01-01",
            content: "alt",
            summarize: "alt",
            user_id: 5,
          })
        );
      }
      return Promise.resolve(jsonResponse({}));
    });
    const user = userEvent.setup();
    renderDashboard(authFetch);

    await screen.findByText("Bearbeitbare Aufnahme");
    await user.click(screen.getByRole("button", { name: "Select-Bearbeitbare Aufnahme" }));
    await screen.findByTestId("transcript-view");
    await user.click(screen.getByRole("button", { name: "SaveRec" }));

    await waitFor(() =>
      expect(authFetch).toHaveBeenCalledWith(
        "/api/v1/records/record/4",
        expect.objectContaining({ method: "PUT" })
      )
    );
    expect(toast.success).toHaveBeenCalledWith("Aufnahme gespeichert");
  });

  it("shows the archive day list instead of the welcome screen in archive mode", async () => {
    const authFetch = buildAuthFetch();
    const user = userEvent.setup();
    renderDashboard(authFetch);

    await screen.findByTestId("sidebar");
    await user.click(screen.getByRole("button", { name: /ToggleArchived/ }));

    await waitFor(() =>
      expect(screen.getByTestId("archive-day-list")).toBeInTheDocument()
    );
    // No date selected yet -> the day list shows its date prompt, not the welcome screen.
    expect(screen.queryByText("Willkommen bei openDox")).not.toBeInTheDocument();
    expect(screen.getByTestId("archive-day-date")).toHaveTextContent("none");
  });

  it("selects an archive date in the sidebar and passes it to the day list", async () => {
    const authFetch = buildAuthFetch();
    const user = userEvent.setup();
    renderDashboard(authFetch);

    await screen.findByTestId("sidebar");
    await user.click(screen.getByRole("button", { name: /ToggleArchived/ }));
    await user.click(await screen.findByRole("button", { name: "PickDate" }));

    expect(screen.getByTestId("archive-date")).toHaveTextContent("2026-09-23");
    expect(screen.getByTestId("archive-day-date")).toHaveTextContent("2026-09-23");
  });

  it("opens a transcript from the archive day list", async () => {
    const authFetch = vi.fn((url: string) => {
      if (url.includes("/records/list-records/")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: 8,
              session_id: "s8",
              title: "Archivierte Aufnahme",
              category_id: null,
              timestamp: "2024-01-01",
              content: "archiv-inhalt",
              summarize: "",
              user_id: 5,
            },
          ])
        );
      }
      if (url.includes("/settings/categories/")) return Promise.resolve(jsonResponse([]));
      if (url.includes("/records/active-session/")) return Promise.resolve(jsonResponse({ active: false }));
      if (url === "/api/v1/records/record/8") {
        return Promise.resolve(
          jsonResponse({
            id: 8,
            session_id: "s8",
            title: "Archivierte Aufnahme",
            category_id: null,
            timestamp: "2024-01-01",
            content: "archiv-inhalt",
            summarize: "",
            user_id: 5,
          })
        );
      }
      return Promise.resolve(jsonResponse({}));
    });
    const user = userEvent.setup();
    renderDashboard(authFetch);

    await screen.findByTestId("sidebar");
    await user.click(screen.getByRole("button", { name: /ToggleArchived/ }));
    await screen.findByTestId("archive-day-list");
    await user.click(screen.getByRole("button", { name: "ArchiveSelect-Archivierte Aufnahme" }));

    expect(await screen.findByText("TranscriptView-Archivierte Aufnahme")).toBeInTheDocument();
  });

  it("unarchives a recording from the archive day list", async () => {
    const authFetch = vi.fn((url: string, options?: RequestInit) => {
      if (url.includes("/records/list-records/")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: 9,
              session_id: "s9",
              title: "Wiederherzustellende Aufnahme",
              category_id: null,
              timestamp: "2024-01-01",
              content: "",
              summarize: "",
              user_id: 5,
            },
          ])
        );
      }
      if (url.includes("/settings/categories/")) return Promise.resolve(jsonResponse([]));
      if (url.includes("/records/active-session/")) return Promise.resolve(jsonResponse({ active: false }));
      if (url === "/api/v1/records/record/9/unarchive" && options?.method === "PUT") {
        return Promise.resolve(jsonResponse({ ok: true }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    const user = userEvent.setup();
    renderDashboard(authFetch);

    await screen.findByTestId("sidebar");
    await user.click(screen.getByRole("button", { name: /ToggleArchived/ }));
    await screen.findByTestId("archive-day-list");
    await user.click(
      screen.getByRole("button", { name: "ArchiveUnarchive-Wiederherzustellende Aufnahme" })
    );

    await waitFor(() =>
      expect(authFetch).toHaveBeenCalledWith("/api/v1/records/record/9/unarchive", { method: "PUT" })
    );
    expect(toast.success).toHaveBeenCalledWith("Aufnahme wiederhergestellt");
  });

  it("clears the archive date selection when toggling back to the library", async () => {
    const authFetch = buildAuthFetch();
    const user = userEvent.setup();
    renderDashboard(authFetch);

    await screen.findByTestId("sidebar");
    await user.click(screen.getByRole("button", { name: /ToggleArchived/ }));
    await user.click(await screen.findByRole("button", { name: "PickDate" }));
    expect(screen.getByTestId("archive-date")).toHaveTextContent("2026-09-23");

    await user.click(screen.getByRole("button", { name: "ToggleArchived-archived" }));

    expect(screen.getByTestId("archive-date")).toHaveTextContent("none");
    expect(screen.queryByTestId("archive-day-list")).not.toBeInTheDocument();
    expect(await screen.findByText("Willkommen bei openDox")).toBeInTheDocument();
  });
});
