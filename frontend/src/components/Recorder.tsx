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

import { useState, useRef, useEffect, forwardRef, useImperativeHandle } from "react";
import { Button } from "@/components/ui/button";
import { Mic, Square, Loader2, Pause, Play } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { BASE_PATH } from "@/api";
import { useAuth } from "@/contexts/AuthContext";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { VoiceVisualizer, BarVisualizer } from "@/components/ui/voice-visualizer";

interface RecorderProps {
  userId: string;
  title?: string;
  categoryId?: string | null;
  patient?: string;
  subject?: string;
  onFinalTranscription?: (sessionId: string, taskId?: string | number) => void;
  onRecordingStart?: (recordingData: any) => void;
  autoStart?: boolean;
  resumeSessionId?: string;
}

export interface RecorderHandle {
  waitForUploads: () => Promise<void>;
}

const Recorder = forwardRef<RecorderHandle, RecorderProps>(({ userId, title, categoryId, patient, subject, onFinalTranscription, onRecordingStart, autoStart, resumeSessionId }, ref) => {
  const { authFetch } = useAuth();
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [stableTranscript, setStableTranscript] = useState("");
  const [isPaused, setIsPaused] = useState(false);
  const [isStopDialogOpen, setIsStopDialogOpen] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const isPausedRef = useRef(false);
  const wsFinishedRef = useRef(false);
  const processingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [liveEnabled, setLiveEnabled] = useState(true);
  const liveTranscriptRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = liveTranscriptRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [stableTranscript, liveTranscript]);

  useImperativeHandle(ref, () => ({
    waitForUploads: async () => {
      // No uploads needed — audio is sent via WebSocket PCM
    },
  }));

  const createRecord = async () => {
    const response = await authFetch("/api/v1/records/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        "user_id": userId,
        "title": title || "Neue Aufnahme",
        "category_id": categoryId ? parseInt(categoryId) : null
      })
    });

    if (!response.ok) throw new Error("Fehler beim Erstellen der Aufnahme");

    const record = await response.json();
    setSessionId(record.session_id);
    sessionIdRef.current = record.session_id;
    toast.success("Aufnahme gestartet");
    if (onRecordingStart) {
      onRecordingStart(record);
    }
    return record;
  };

  const openWebSocket = (userId: string, session_id: string) => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const token = localStorage.getItem("access_token") || "";
    const ws = new WebSocket(
      `${protocol}//${window.location.host}${BASE_PATH}/api/v1/records/ws/record?session_id=${session_id}&user_id=${userId}&token=${encodeURIComponent(token)}`
    );
    socketRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket verbunden");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.partial) {
        setLiveTranscript(data.partial);
      }

      if (data.cleanup !== undefined) {
        // Periodic LLM cleanup replaced the full stable transcript
        setStableTranscript(data.cleanup);
        setLiveTranscript("");
      }

      if (data.text !== undefined) {
        if (data.restored) {
          // Resume: backend replays the accumulated transcript - set, don't append.
          setStableTranscript(data.text);
        } else {
          setStableTranscript((prev) =>
            (prev + " " + data.text).trim()
          );
        }
        setLiveTranscript("");
      }

      if (data.status === "finished" || data.status === "error") {
        wsFinishedRef.current = true;
        if (processingTimeoutRef.current) {
          clearTimeout(processingTimeoutRef.current);
          processingTimeoutRef.current = null;
        }
        setIsProcessing(false);
        if (data.status === "finished") {
          toast.success("Aufnahme wird verarbeitet...");
        }
        if (onFinalTranscription) {
          onFinalTranscription(sessionIdRef.current || "", data.task_id);
        }
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket Fehler:", error);
      toast.error("WebSocket Fehler");
    };

    ws.onclose = () => {
      console.log("WebSocket geschlossen");
      if (!wsFinishedRef.current) {
        // Unexpected disconnect (e.g. Apache proxy dropped the connection).
        // The recording may still finish server-side (finalize() doesn't
        // depend on this socket) — fall back to fetching the record by
        // session id so the frontend picks up its task_id and starts
        // polling for the transcript instead of getting stuck empty.
        //
        // Also tear down the local capture pipeline (mirrors stopRecording()) —
        // otherwise the mic stream / AudioWorklet / AudioContext keep running
        // in the background with nothing consuming their output, burning CPU
        // until the tab is closed.
        try { workletRef.current?.disconnect(); } catch (_) {}
        try { streamRef.current?.getTracks().forEach((track) => track.stop()); } catch (_) {}
        try { audioContextRef.current?.close(); } catch (_) {}
        setAnalyser(null);

        setIsRecording(false);
        setIsProcessing(false);
        if (processingTimeoutRef.current) {
          clearTimeout(processingTimeoutRef.current);
          processingTimeoutRef.current = null;
        }
        toast.error("Verbindung unterbrochen – bitte Aufnahme neu starten");
        if (onFinalTranscription && sessionIdRef.current) {
          onFinalTranscription(sessionIdRef.current, undefined);
        }
      }
      wsFinishedRef.current = false;
    };
  };

  const startRecording = async () => {
    try {
      let record;

      // Resume an existing unfinished session or create a new recording.
      if (resumeSessionId) {
        // Reuse the existing session_id - backend restores the live transcript
        // and new audio is appended to the same session.
        record = { session_id: resumeSessionId };
        setSessionId(resumeSessionId);
        sessionIdRef.current = resumeSessionId;
      } else {
        record = await createRecord();
      }

      openWebSocket(userId, record.session_id);

      // 1) User-Audio holen
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        }
      });
      streamRef.current = stream;

      // 2) AudioContext + Worklet + Visualizer
      const audioCtx = new AudioContext({ sampleRate: 16000 });
      if (audioCtx.state === "suspended") {
        await audioCtx.resume();
      }

      // Analyser for Visualization
      const analyserNode = audioCtx.createAnalyser();
      analyserNode.fftSize = 256;
      setAnalyser(analyserNode);

      // Inline Worklet: Garantiert, dass der Code geladen wird und Float32 -> Int16 konvertiert
      const workletCode = `
        class PCMProcessor extends AudioWorkletProcessor {
          process(inputs, outputs, parameters) {
            const input = inputs[0];
            if (input.length > 0) {
              // Sende rohes Float32 (4 Byte pro Sample) direkt an das Backend
              this.port.postMessage(input[0].buffer);
            }
            return true;
          }
        }
        registerProcessor("pcm-worklet", PCMProcessor);
      `;
      const blob = new Blob([workletCode], { type: "application/javascript" });
      const workletUrl = URL.createObjectURL(blob);
      await audioCtx.audioWorklet.addModule(workletUrl);

      const source = audioCtx.createMediaStreamSource(stream);
      const worklet = new AudioWorkletNode(audioCtx, "pcm-worklet");

      // Float32 → WebSocket
      worklet.port.onmessage = (e) => {
        if (socketRef.current?.readyState === WebSocket.OPEN && !isPausedRef.current) {
          socketRef.current.send(e.data);
        }
      };

      // Connect Graph
      source.connect(analyserNode); // source -> analyser
      // source.connect(worklet); // source -> worklet (Using separate connection?)
      // Actually, we can connect source to multiple destinations
      source.connect(worklet);
      // We don't connect to destination (speakers) to avoid feedback loop unless desired

      audioContextRef.current = audioCtx;
      workletRef.current = worklet;
      setIsRecording(true);
      setIsPaused(false);
      isPausedRef.current = false;
      setIsProcessing(false);
    } catch (err) {
      console.error(err);
      toast.error("Fehler beim Starten der Aufnahme");
    }
  };

  const stopRecording = () => {
    if (!isRecording) return;

    isPausedRef.current = false;

    try { workletRef.current?.disconnect(); } catch (_) {}
    streamRef.current?.getTracks().forEach(track => track.stop());
    audioContextRef.current?.close();
    setAnalyser(null);

    setIsRecording(false);
    setIsPaused(false);
    isPausedRef.current = false;
    setIsProcessing(true);

    if (socketRef.current?.readyState === WebSocket.OPEN) {
      wsFinishedRef.current = false;
      socketRef.current.send(JSON.stringify({ event: "stop" }));
      // Safety timeout: reset spinner if backend never responds
      processingTimeoutRef.current = setTimeout(() => {
        setIsProcessing(false);
        toast.error("Zeitüberschreitung – Aufnahme konnte nicht verarbeitet werden");
      }, 90_000);
    } else {
      setIsProcessing(false);
      toast.error("Verbindung bereits unterbrochen");
    }
  };

  const pauseSession = () => {
    if (!isRecording) return;
    isPausedRef.current = true;
    audioContextRef.current?.suspend();
    setIsPaused(true);
  };

  const resumeSession = () => {
    audioContextRef.current?.resume();
    setIsPaused(false);
    isPausedRef.current = false;
  };

  const handleStopClick = () => {
    setIsStopDialogOpen(true);
  };

  const confirmStop = () => {
    setIsStopDialogOpen(false);
    stopRecording();
  };

  useEffect(() => {
    // Load settings to determine if live transcription is enabled
    fetch("/api/v1/settings/whisper-settings/")
      .then((res) => res.json())
      .then((data) => {
        setLiveEnabled(data.live_backend !== "disabled");
      })
      .catch(() => setLiveEnabled(true));
  }, []);

  useEffect(() => {
    // Resume an existing unfinished session or auto-start a new recording.
    // The server (session_store) holds the live state across reconnects.
    if (resumeSessionId || autoStart) {
      startRecording();
    }

    return () => {
      // On unmount without stopping (e.g. "Zur Übersicht"): tear down capture and
      // close the socket as a plain disconnect -> backend keeps the session so it
      // can be resumed later.
      isPausedRef.current = true;
      try { workletRef.current?.disconnect(); } catch (_) {}
      try { streamRef.current?.getTracks().forEach((t) => t.stop()); } catch (_) {}
      try { audioContextRef.current?.close(); } catch (_) {}
      try { socketRef.current?.close(); } catch (_) {}
    };
  }, []);

  return (
    <div className="flex flex-col w-full h-full items-center justify-start p-6 bg-background dark:bg-zinc-950 transition-colors duration-300">

      {/* Main Card */}
      <div className="w-full max-w-5xl bg-card border border-border shadow-sm rounded-xl overflow-hidden flex flex-col h-[85dvh]">

        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between flex-wrap gap-2 bg-zinc-50/50 dark:bg-zinc-900/50">
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-2.5 h-2.5 rounded-full transition-all duration-300",
              isRecording ? "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)] animate-pulse" : "bg-zinc-300 dark:bg-zinc-700"
            )}></div>
            <span className="font-medium text-sm text-foreground/80 tracking-tight">
              {isPaused ? "Aufnahme pausiert" : isRecording ? "Aufnahme läuft..." : "Aufnahme bereit"}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {patient && (
              <div className="px-3 py-1 bg-primary/10 text-primary text-xs font-medium rounded-full border border-primary/20">
                {patient}
              </div>
            )}
            {subject && (
              <div className="px-3 py-1 bg-secondary text-secondary-foreground text-xs font-medium rounded-full border border-border">
                {subject}
              </div>
            )}
          </div>
        </div>

        {/* Transcription Area */}
        <div ref={liveTranscriptRef} className="flex-1 overflow-y-auto p-8 font-sans">
          {liveEnabled ? (
            <div className="w-full max-w-3xl mx-auto space-y-2">
              <p className="text-xs text-muted-foreground/70 text-center italic">
                Live-Vorschau dient nur der groben Übersicht während der Aufnahme — nicht das endgültige Transkriptionsergebnis.
              </p>
              {stableTranscript || liveTranscript ? (
                <p
                  className="select-none text-base md:text-lg font-light leading-relaxed text-foreground/90 tracking-wide"
                  onCopy={(e) => e.preventDefault()}
                >
                  {stableTranscript}
                  {liveTranscript && (
                    <span className="text-primary/70 animate-pulse font-normal ml-1 border-b border-primary/30 pb-0.5">
                      {liveTranscript}
                    </span>
                  )}
                </p>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-muted-foreground/40 mt-20">
                  <p className="text-lg font-light">Sprechen Sie, um die Transkription zu starten</p>
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center">
              {isRecording && !isPaused && (
                <VoiceVisualizer analyser={analyser} />
              )}
            </div>
          )}
        </div>

        {/* Live bar spectrum, next to the live transcript */}
        {liveEnabled && isRecording && !isPaused && (
          <div className="w-full flex justify-center pb-2 bg-gradient-to-t from-background/50 to-transparent">
            <BarVisualizer analyser={analyser} />
          </div>
        )}

        {/* Footer / Controls */}
        <div className="p-8 border-t border-border bg-zinc-50/30 dark:bg-zinc-900/30 flex justify-center items-center gap-6">
          {!isProcessing ? (
            <>
              {isRecording && (
                <Button
                  onClick={isPaused ? resumeSession : pauseSession}
                  variant="outline"
                  className={cn(
                    "w-16 h-16 rounded-full border-2 transition-all duration-300",
                    isPaused
                      ? "border-primary text-primary hover:bg-primary/10"
                      : "border-amber-500 text-amber-500 hover:bg-amber-500/10"
                  )}
                >
                  {isPaused ? <Play className="w-6 h-6 fill-current" /> : <Pause className="w-6 h-6 fill-current" />}
                </Button>
              )}

              <Button
                onClick={isRecording ? handleStopClick : startRecording}
                className={cn(
                  "group relative w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 transform hover:scale-105 active:scale-95 shadow-md",
                  isRecording
                    ? "bg-red-500 hover:bg-red-600 shadow-red-500/20"
                    : "bg-primary hover:bg-primary/90 shadow-primary/25"
                )}
              >
                {isRecording ? (
                  <Square className="w-8 h-8 text-white fill-current" />
                ) : (
                  <Mic className="w-8 h-8 text-white group-hover:animate-wiggle" />
                )}

                {/* Pulse Ring for Recording State */}
                {isRecording && (
                  <span className="absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-20 animate-ping"></span>
                )}
              </Button>
            </>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
              <span className="text-sm font-medium text-muted-foreground animate-pulse">Verarbeite Aufnahme...</span>
            </div>
          )}
        </div>
      </div>

      <Dialog open={isStopDialogOpen} onOpenChange={setIsStopDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aufnahme beenden</DialogTitle>
            <DialogDescription>
              Möchten Sie die Aufnahme wirklich beenden und speichern?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsStopDialogOpen(false)}>
              Abbrechen
            </Button>
            <Button onClick={confirmStop}>
              Aufnahme beenden
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );

});

export default Recorder;
