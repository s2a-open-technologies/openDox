import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Mic, Square, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface RecorderProps {
  onTranscriptReceived: (transcript: string) => void;
}

const Recorder = ({ onTranscriptReceived }: RecorderProps) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(chunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach((track) => track.stop());
        await uploadAudio(audioBlob);
      };

      mediaRecorder.start();
      setIsRecording(true);
      toast.success("Aufnahme gestartet");
    } catch (error) {
      toast.error("Mikrofonzugriff verweigert");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setIsProcessing(true);
    }
  };

  const uploadAudio = async (audioBlob: Blob) => {
    try {
      // Mock upload - replace with real API call
      // const formData = new FormData();
      // formData.append("audio", audioBlob);
      // const response = await fetch("/api/upload", { method: "POST", body: formData });
      // const data = await response.json();
      
      // Mock response for demonstration
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const mockTranscript = "Dies ist ein Beispieltranskript. Ersetzen Sie dies mit einem echten Backend-Aufruf an /api/upload.";
      
      onTranscriptReceived(mockTranscript);
      toast.success("Transkript erfolgreich erstellt");
    } catch (error) {
      toast.error("Fehler beim Hochladen");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex items-center justify-center h-full p-8">
      <div className="text-center space-y-8 max-w-md">
        {!isRecording && !isProcessing && (
          <div className="space-y-4">
            <h2 className="text-2xl font-semibold text-foreground">Keine Aufnahme aktiv</h2>
            <p className="text-muted-foreground">
              Klicken Sie auf den Button, um eine neue Aufnahme zu starten
            </p>
          </div>
        )}

        {isRecording && (
          <div className="space-y-4">
            <h2 className="text-2xl font-semibold text-foreground">Aufnahme läuft...</h2>
            <div className="flex items-center justify-center gap-1">
              <div className="w-2 h-2 bg-recording-pulse rounded-full animate-pulse" />
              <div
                className="w-2 h-2 bg-recording-pulse rounded-full animate-pulse"
                style={{ animationDelay: "0.2s" }}
              />
              <div
                className="w-2 h-2 bg-recording-pulse rounded-full animate-pulse"
                style={{ animationDelay: "0.4s" }}
              />
            </div>
          </div>
        )}

        {isProcessing && (
          <div className="space-y-4">
            <h2 className="text-2xl font-semibold text-foreground">Verarbeitung läuft...</h2>
            <Loader2 className="w-8 h-8 text-primary animate-spin mx-auto" />
          </div>
        )}

        <div className="flex justify-center">
          {!isRecording ? (
            <Button
              onClick={startRecording}
              disabled={isProcessing}
              size="lg"
              className={cn(
                "w-24 h-24 rounded-full",
                !isProcessing && "hover:scale-110 transition-transform"
              )}
            >
              {isProcessing ? (
                <Loader2 className="w-10 h-10 animate-spin" />
              ) : (
                <Mic className="w-10 h-10" />
              )}
            </Button>
          ) : (
            <Button
              onClick={stopRecording}
              size="lg"
              variant="destructive"
              className="w-24 h-24 rounded-full relative hover:scale-110 transition-transform"
            >
              <Square className="w-10 h-10" />
              <div className="absolute inset-0 rounded-full bg-recording-pulse/20 animate-ping" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default Recorder;
