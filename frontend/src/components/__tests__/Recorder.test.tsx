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

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Recorder from "@/components/Recorder";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";

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

/**
 * jsdom has no working WebSocket. This fake exposes the same
 * onopen/onmessage/onclose/onerror/send/close surface Recorder.tsx drives,
 * defaults to an already-OPEN connection (readyState checks in the
 * component gate `send()` on `WebSocket.OPEN`), and records every outgoing
 * message so tests can assert on it.
 */
class FakeWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  url: string;
  readyState = FakeWebSocket.OPEN;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: ((error: unknown) => void) | null = null;
  sent: unknown[] = [];

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: unknown) {
    this.sent.push(data);
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED;
  }
}

class FakeAudioWorkletNode {
  static instances: FakeAudioWorkletNode[] = [];
  port: { onmessage: ((e: { data: unknown }) => void) | null } = { onmessage: null };
  disconnect = vi.fn();
  constructor() {
    FakeAudioWorkletNode.instances.push(this);
  }
}

class FakeAudioContext {
  static instances: FakeAudioContext[] = [];
  state = "running";
  audioWorklet = { addModule: vi.fn().mockResolvedValue(undefined) };
  resume = vi.fn().mockResolvedValue(undefined);
  suspend = vi.fn().mockResolvedValue(undefined);
  close = vi.fn().mockResolvedValue(undefined);
  constructor() {
    FakeAudioContext.instances.push(this);
  }
  createAnalyser() {
    return { fftSize: 0, connect: vi.fn(), getByteFrequencyData: vi.fn() };
  }
  createMediaStreamSource() {
    return { connect: vi.fn() };
  }
}

function makeStream(stopTrack = vi.fn()) {
  return { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream;
}

function setupMediaMocks() {
  vi.stubGlobal("WebSocket", FakeWebSocket);
  vi.stubGlobal("AudioContext", FakeAudioContext);
  vi.stubGlobal("AudioWorkletNode", FakeAudioWorkletNode);
  URL.createObjectURL = vi.fn(() => "blob:mock");
  URL.revokeObjectURL = vi.fn();
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia: vi.fn().mockResolvedValue(makeStream()) },
    configurable: true,
  });
}

function renderRecorder(
  props: Partial<React.ComponentProps<typeof Recorder>> = {},
  authFetch: ReturnType<typeof vi.fn> = vi
    .fn()
    .mockResolvedValue(jsonResponse({ session_id: "sess-abc" }))
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

  return render(<Recorder userId="1" {...props} />);
}

describe("Recorder", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    FakeWebSocket.instances = [];
    FakeAudioWorkletNode.instances = [];
    FakeAudioContext.instances = [];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ live_backend: "parakeet" }))
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete (URL as unknown as Record<string, unknown>).createObjectURL;
    delete (URL as unknown as Record<string, unknown>).revokeObjectURL;
  });

  it("renders the idle state with patient/subject badges and a single mic button", () => {
    renderRecorder({ patient: "Max Mustermann", subject: "Anamnese" });

    expect(screen.getByText("Aufnahme bereit")).toBeInTheDocument();
    expect(screen.getByText("Max Mustermann")).toBeInTheDocument();
    expect(screen.getByText("Anamnese")).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("does not render a 'Kein Medizinprodukt' disclaimer itself", () => {
    // Documented in AGENTS.md as required "in the recording dialog", but the
    // actual disclaimer text lives in Dashboard.tsx's "Neue Aufnahme" dialog
    // (and in TranscriptView.tsx) that wraps/precedes this component, not in
    // Recorder.tsx's own markup. Asserted here so a future refactor that
    // silently drops the dialog's disclaimer doesn't go unnoticed at this layer.
    renderRecorder();
    expect(screen.queryByText("Kein Medizinprodukt")).not.toBeInTheDocument();
  });

  it("creates a record, opens the WebSocket and requests the microphone on start", async () => {
    setupMediaMocks();
    const authFetch = vi.fn().mockResolvedValue(jsonResponse({ session_id: "sess-abc" }));
    const onRecordingStart = vi.fn();
    const user = userEvent.setup();
    renderRecorder({ onRecordingStart }, authFetch);

    await user.click(screen.getByRole("button"));

    await waitFor(() =>
      expect(authFetch).toHaveBeenCalledWith(
        "/api/v1/records/create",
        expect.objectContaining({ method: "POST" })
      )
    );
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    expect(FakeWebSocket.instances[0].url).toContain("session_id=sess-abc");
    expect(FakeWebSocket.instances[0].url).toContain("user_id=1");
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(1);
    expect(onRecordingStart).toHaveBeenCalledWith(expect.objectContaining({ session_id: "sess-abc" }));
    await waitFor(() => expect(screen.getByText("Aufnahme läuft...")).toBeInTheDocument());
  });

  it("resumes an existing session without creating a new record", async () => {
    setupMediaMocks();
    const authFetch = vi.fn();
    renderRecorder({ resumeSessionId: "sess-existing", autoStart: false }, authFetch);

    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    expect(FakeWebSocket.instances[0].url).toContain("session_id=sess-existing");
    expect(authFetch).not.toHaveBeenCalledWith(
      "/api/v1/records/create",
      expect.anything()
    );
  });

  it("relays partial and committed WebSocket messages into the live transcript", async () => {
    setupMediaMocks();
    const user = userEvent.setup();
    renderRecorder();

    await user.click(screen.getByRole("button"));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    const ws = FakeWebSocket.instances[0];

    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ partial: "Hallo Wel" }) });
    });
    expect(screen.getByText("Hallo Wel")).toBeInTheDocument();

    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ text: "Hallo Welt." }) });
    });
    expect(screen.getByText("Hallo Welt.")).toBeInTheDocument();

    const onFinalTranscription = vi.fn();
    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ status: "finished", task_id: 42 }) });
    });
    expect(toast.success).toHaveBeenCalledWith("Aufnahme wird verarbeitet...");
    void onFinalTranscription;
  });

  it("shows an error toast and tears down capture on an unexpected WebSocket close", async () => {
    setupMediaMocks();
    const onFinalTranscription = vi.fn();
    const user = userEvent.setup();
    renderRecorder({ onFinalTranscription });

    await user.click(screen.getByRole("button"));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    await waitFor(() => expect(FakeAudioWorkletNode.instances).toHaveLength(1));
    const ws = FakeWebSocket.instances[0];
    const worklet = FakeAudioWorkletNode.instances[0];

    act(() => {
      ws.onclose?.();
    });

    expect(toast.error).toHaveBeenCalledWith("Verbindung unterbrochen – bitte Aufnahme neu starten");
    expect(worklet.disconnect).toHaveBeenCalled();
    expect(onFinalTranscription).toHaveBeenCalledWith("sess-abc", undefined);
    await waitFor(() => expect(screen.getByText("Aufnahme bereit")).toBeInTheDocument());
  });

  it("shows the server's specific message when a resumed recording cannot continue here", async () => {
    setupMediaMocks();
    const onFinalTranscription = vi.fn();
    const user = userEvent.setup();
    renderRecorder({ onFinalTranscription });

    await user.click(screen.getByRole("button"));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    await waitFor(() => expect(FakeAudioWorkletNode.instances).toHaveLength(1));
    const ws = FakeWebSocket.instances[0];
    const worklet = FakeAudioWorkletNode.instances[0];

    act(() => {
      ws.onmessage?.({
        data: JSON.stringify({
          error: "Earlier audio of this recording is not available on this server instance",
          code: "recording_audio_unavailable",
        }),
      });
      ws.onclose?.();
    });

    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("anderen Server-Instanz")
    );
    // Not the generic message on top, and no polling for a transcript that will never come.
    expect(toast.error).not.toHaveBeenCalledWith(
      "Verbindung unterbrochen – bitte Aufnahme neu starten"
    );
    expect(onFinalTranscription).not.toHaveBeenCalled();
    // The capture pipeline is still shut down.
    expect(worklet.disconnect).toHaveBeenCalled();
    await waitFor(() => expect(screen.getByText("Aufnahme bereit")).toBeInTheDocument());
  });

  it("ignores an error message without a code (existing auth errors keep their behaviour)", async () => {
    setupMediaMocks();
    const onFinalTranscription = vi.fn();
    const user = userEvent.setup();
    renderRecorder({ onFinalTranscription });

    await user.click(screen.getByRole("button"));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    const ws = FakeWebSocket.instances[0];

    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ error: "Invalid or expired token" }) });
      ws.onclose?.();
    });

    expect(toast.error).toHaveBeenCalledWith(
      "Verbindung unterbrochen – bitte Aufnahme neu starten"
    );
    expect(onFinalTranscription).toHaveBeenCalledWith("sess-abc", undefined);
  });

  it("confirms the stop dialog, sends the stop event and shows the processing spinner", async () => {
    setupMediaMocks();
    const user = userEvent.setup();
    renderRecorder();

    await user.click(screen.getByRole("button"));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    const ws = FakeWebSocket.instances[0];

    // Two buttons while recording: pause/resume + stop.
    const buttons = screen.getAllByRole("button");
    const stopButton = buttons.find((btn) => btn.querySelector("svg.lucide-square"));
    await user.click(stopButton!);

    expect(screen.getByRole("heading", { name: "Aufnahme beenden" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Aufnahme beenden" }));

    expect(ws.sent).toContainEqual(JSON.stringify({ event: "stop" }));
    await waitFor(() => expect(screen.getByText("Verarbeite Aufnahme...")).toBeInTheDocument());
  });
});
