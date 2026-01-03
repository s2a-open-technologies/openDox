import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Mic, Square, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface RecorderProps {
  userId: string;
  title?: string;
  onFinalTranscription?: (text: string) => void;
  autoStart?: boolean;
}

const Recorder = ({ userId, title, onFinalTranscription, autoStart }: RecorderProps) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [stableTranscript, setStableTranscript] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const finalChunksRef = useRef<Blob[]>([]);

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
          onFinalTranscription(stableTranscript);
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
      const record = await createRecord();
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
        socketRef.current?.send(JSON.stringify({ event: "stop" }));
        setIsProcessing(true);
        // hier kannst du später finalChunksRef zusammenführen und hochladen
      };

      // alle 1000 ms Chunk für finale Datei
      mediaRecorder.start(10000);

      audioContextRef.current = audioCtx;
      workletRef.current = worklet;
      setIsRecording(true);
      setIsProcessing(false);
    } catch (err) {
      console.error(err);
      toast.error("Fehler beim Starten der Aufnahme");
    }
  };

  const stopRecording = () => {
    if (!isRecording) return;

    // MediaRecorder stoppen → triggert onstop
    mediaRecorderRef.current?.stop();

    // Worklet & AudioContext aufräumen
    try {
      workletRef.current?.disconnect();
    } catch (_) {
      // ignore
    }

    audioContextRef.current?.close();

    setIsRecording(false);
  };

  // Function for uploading Wav chunks to the background
  const uploadChunk = async (chunk: Blob, sessionId: string) => {
    const formData = new FormData();
    formData.append("audio", chunk, `chunk_${Date.now()}_${sessionId}_${userId}.webm`);
    formData.append("session_id", sessionId);

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

  useEffect(() => {
    if (autoStart) {
      startRecording();
    }
  }, []);

  return (
    <div className="flex flex-col items-center p-8 w-full h-full gap-4">

      {/* Live Container */}
      {isRecording && (
        <div className="w-full max-w-lg bg-background border rounded-lg p-4 shadow-sm">
          <h2 className="text-lg font-semibold mb-2">Live-Transkription</h2>
          <p className="text-muted-foreground min-h-[80px]">
            {stableTranscript}
            {liveTranscript && (
              <span className="opacity-50"> {liveTranscript}</span>
            )}
          </p>
        </div>
      )}

      {/* BUTTON-BEREICH → IMMER vertikal zentriert */}
      <div className="flex-1 flex items-center justify-center w-full">
        {!isProcessing ? (
          <Button
            onClick={isRecording ? stopRecording : startRecording}
            size="lg"
            className={cn(
              "w-20 h-20 rounded-full",
              !isRecording && "hover:scale-110 transition-transform"
            )}
          >
            {isRecording ? (
              <Square className="w-10 h-10" />
            ) : (
              <Mic className="w-10 h-10" />
            )}
          </Button>
        ) : (
          <div className="flex flex-col items-center">
            <Loader2 className="w-10 h-10 animate-spin text-primary" />
            <p className="text-muted-foreground mt-2">Verarbeitung…</p>
          </div>
        )}
      </div>

    </div>
  );

};

export default Recorder;
