import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Mic, Square, Loader2, Pause, Play } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface RecorderProps {
  userId: string;
  title?: string;
  patient?: string;
  subject?: string;
  onFinalTranscription?: (text: string, taskId?: string | number) => void;
  onRecordingStart?: (recordingData: any) => void;
  autoStart?: boolean;
}

const Recorder = ({ userId, title, patient, subject, onFinalTranscription, onRecordingStart, autoStart }: RecorderProps) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [stableTranscript, setStableTranscript] = useState("");
  const [isPaused, setIsPaused] = useState(false);
  const [isStopDialogOpen, setIsStopDialogOpen] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const finalChunksRef = useRef<Blob[]>([]);

  const isPausedRef = useRef(false);

  const createRecord = async () => {
    const response = await fetch("/api/v1/records/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        "user_id": userId,
        "title": title || "Neue Aufnahme"
      })
    });

    if (!response.ok) throw new Error("Fehler beim Erstellen der Aufnahme");

    const record = await response.json();
    setSessionId(record.session_id);
    toast.success("Aufnahme gestartet");
    if (onRecordingStart) {
      onRecordingStart(record);
    }
    // Save to localStorage
    localStorage.setItem("currentSession", JSON.stringify(record));
    return record;
  };

  const openWebSocket = (userId: string, session_id: string) => {
    const ws = new WebSocket(
      `ws://localhost:5000/api/v1/records/ws/record?session_id=${session_id}&user_id=${userId}`
    );
    socketRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket verbunden");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      // PARTIAL -> nur anzeigen
      if (data.partial) {
        setLiveTranscript(data.partial);
      }

      // FINAL -> an stableTranscript anhängen
      if (data.text) {
        setStableTranscript((prev) =>
          (prev + " " + data.text).trim()
        );
        setLiveTranscript(""); // Clear the preview
      }

      if (data.status === "finished") {
        setIsProcessing(false);
        toast.success("Transkription abgeschlossen");
        if (onFinalTranscription) {
          onFinalTranscription(stableTranscript, data.task_id);
        }
      }
    };


    ws.onerror = (error) => {
      console.error("WebSocket Fehler:", error);
      toast.error("WebSocket Fehler");
    };

    ws.onclose = () => {
      console.log("WebSocket geschlossen");
    };
  };

  const startRecording = async () => {
    try {
      let record;
      const savedSession = localStorage.getItem("currentSession");

      // Resume logic or New Recording
      if (savedSession) {
        record = JSON.parse(savedSession);
        setSessionId(record.session_id);
        // If we are resuming, we might want to notify or just proceed
        // Assuming 'title' etc are still valid
        if (onRecordingStart && !sessionId) {
          onRecordingStart(record); // ensure sidebar is updated if it was a reload
        }
      } else {
        record = await createRecord();
      }

      openWebSocket(userId, record.session_id); // Verwende userId und session_id

      // 1) User Audio holen
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,      // Zwingend Mono für Whisper
          sampleRate: 16000,    // Versuch, direkt 16kHz zu bekommen
          echoCancellation: true,
          noiseSuppression: true,
        }
      });

      // 2) AudioContext + Worklet
      const audioCtx = new AudioContext({ sampleRate: 16000 });
      if (audioCtx.state === "suspended") {
        await audioCtx.resume();
      }

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
        if (socketRef.current?.readyState === WebSocket.OPEN) {
          socketRef.current.send(e.data); // ArrayBuffer (Float32)
        }
      };

      source.connect(worklet);

      // MediaRecorder für finale Datei
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mediaRecorder;
      finalChunksRef.current = []; // reset

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0 && sessionId) {
          uploadChunk(e.data, sessionId);
        }
      };

      mediaRecorder.onstop = () => {
        // If paused, do NOT send stop event and do NOT show processing
        if (isPausedRef.current) {
          console.log("Recording paused - waiting for resume");
          return;
        }

        socketRef.current?.send(JSON.stringify({ event: "stop" }));
        setIsProcessing(true);
        // hier kannst du später finalChunksRef zusammenführen und hochladen
      };

      // alle 10s Chunk für finale Datei (Upload)
      mediaRecorder.start(10000);

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

    // Explicitly mark as NOT paused (we are stopping)
    isPausedRef.current = false;

    // MediaRecorder stoppen → triggert onstop
    mediaRecorderRef.current?.stop();

    // Worklet & AudioContext aufräumen
    try {
      workletRef.current?.disconnect();
    } catch (_) {
      // ignore
    }

    audioContextRef.current?.close();

    // WebSocket schließen - WAIT! If we close immediately, we might miss the 'finished' message?
    // record.py logic: if we send "stop", it breaks loop, sends "finished", then closes.
    // So we should NOT close it here manually if we want to receive "finished".
    // But `openWebSocket` sets `onclose`.
    // Let's keep it open until "finished" OR timeout?
    // The previous code closed it immediately.
    // If we close it, the backend sees disconnect.
    // Backend says: `if client_connected: await websocket.send_json({"status": "finished"...})`
    // So we MUST NOT close it here.

    // REMOVED explicit socket close here. Let the backend close it or close on unmount.
    // But we need to cleanup references.
    // If we don't close, when do we close?
    // Backend closes it after sending finished.

    // Reset session
    localStorage.removeItem("currentSession");

    setIsRecording(false);
    setIsPaused(false);
    isPausedRef.current = false;
  };

  // Function for uploading Wav chunks to the background
  const uploadChunk = async (chunk: Blob, sessionId: string) => {
    const formData = new FormData();
    formData.append("audio", chunk, `chunk_${Date.now()}_${sessionId}_${userId}.webm`);
    formData.append("session_id", sessionId);
    formData.append("user_id", userId);

    try {
      await fetch("/api/v1/records/record/upload-chunk", {
        method: "POST",
        body: formData
      });
    } catch (err) {
      console.error("Error sending chunks: ", err)
      toast.error("Error sending chunks")
    }
  }



  // Re-implementing Pause correctly
  // Re-implementing Pause correctly
  const pauseSession = () => {
    if (!isRecording) return;

    isPausedRef.current = true; // Mark intent

    // Pause capturing
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.pause();
    }

    // Suspend AudioContext
    if (audioContextRef.current && audioContextRef.current.state === "running") {
      audioContextRef.current.suspend();
    }

    setIsPaused(true);
  };

  // Updated resumeSession: resume MediaRecorder and AudioContext, WebSocket stays open
  const resumeSession = () => {
    // Resume AudioContext if it was suspended
    if (audioContextRef.current?.state === "suspended") {
      audioContextRef.current.resume();
    }
    // Resume MediaRecorder if it was paused
    if (mediaRecorderRef.current?.state === "paused") {
      mediaRecorderRef.current.resume();
    }
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

  // NOTE: I am rewriting the `pauseSession` and `resumeSession` completely to use `suspend/resume` and `MediaRecorder.pause()`.
  // This is much better than restarting the whole stack.


  if (socketRef.current) {
    // We keep socket open.
  }




  useEffect(() => {
    // Check persistence on mount
    const savedSession = localStorage.getItem("currentSession");
    if (savedSession) {
      // Restore state
      const record = JSON.parse(savedSession);
      setSessionId(record.session_id);
      setIsRecording(true);
      setIsPaused(true); // Default to paused on restore

      // Notify parent to show active state in sidebar
      if (onRecordingStart) onRecordingStart(record);
    } else if (autoStart) {
      startRecording();
    }
  }, []);

  return (
    <div className="flex flex-col w-full h-full items-center justify-start p-6 bg-background dark:bg-zinc-950 transition-colors duration-300">

      {/* Main Card */}
      <div className="w-full max-w-5xl bg-card border border-border shadow-sm rounded-xl overflow-hidden flex flex-col h-[85vh]">

        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-zinc-50/50 dark:bg-zinc-900/50">
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
        <div className="flex-1 overflow-y-auto p-8 font-sans">
          <div className="w-full max-w-3xl mx-auto space-y-2">
            {stableTranscript || liveTranscript ? (
              <p className="text-xl md:text-2xl font-light leading-relaxed text-foreground/90 tracking-wide selection:bg-primary/20">
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
        </div>

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

};

export default Recorder;
