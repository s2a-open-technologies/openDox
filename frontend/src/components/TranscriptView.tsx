import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Mic, Check, Loader2, AlertCircle } from "lucide-react";
import { TfiReload } from "react-icons/tfi";
import type { Recording } from "@/pages/Dashboard";
import { cn } from "@/lib/utils";

interface TranscriptViewProps {
  transcript: Recording | null;
  onNewRecording: () => void;
}

const TranscriptView = ({ transcript, onNewRecording }: TranscriptViewProps) => {
  const [taskStatus, setTaskStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!transcript?.taskId) {
      setTaskStatus(null);
      return;
    }

    // Initial check
    checkStatus();

    const interval = setInterval(checkStatus, 2000);
    return () => clearInterval(interval);

    async function checkStatus() {
      if (!transcript?.taskId) return;
      try {
        const res = await fetch(`/api/v1/records/status/${transcript.taskId}`);
        if (res.ok) {
          const data = await res.json();
          setTaskStatus(data.status);
          if (data.status === 'finished' || data.status === 'error') {
            clearInterval(interval);
          }
        }
      } catch (e) {
        console.error("Status check failed", e);
      }
    }
  }, [transcript]);

  if (!transcript) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-8">
        <div className="mb-4">
          <Mic className="w-16 h-16 text-muted-foreground" />
        </div>
        <h2 className="text-2xl font-semibold text-foreground mb-2">Keine Aufnahme ausgewählt</h2>
        <p className="text-muted-foreground mb-6">Wählen Sie eine Aufnahme aus der Seitenleiste aus, um das Transkript anzuzeigen.</p>
        <Button onClick={onNewRecording}>
          <Mic className="w-4 h-4 mr-2" />
          Neue Aufnahme starten
        </Button>
      </div>
    );
  }

  const getStatusBadge = () => {
    if (!taskStatus) return null;

    switch (taskStatus) {
      case 'running':
      case 'transcribing':
        return (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-100 text-red-700 border border-red-200 animate-pulse dark:bg-red-900/30 dark:text-red-400 dark:border-red-900">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span className="text-xs font-semibold">Transkription läuft...</span>
          </div>
        );
      case 'processing_llm':
        return (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-yellow-100 text-yellow-700 border border-yellow-200 animate-pulse dark:bg-yellow-900/30 dark:text-yellow-400 dark:border-yellow-900">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span className="text-xs font-semibold">KI arbeitet...</span>
          </div>
        );
      case 'finished':
        return (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-100 text-green-700 border border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-900">
            <Check className="w-3 h-3" />
            <span className="text-xs font-semibold">Fertig</span>
          </div>
        );
      case 'error':
        return (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-100 text-red-700 border border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-900">
            <AlertCircle className="w-3 h-3" />
            <span className="text-xs font-semibold">Fehler</span>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="h-full p-8 space-y-6 bg-background">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-3xl font-bold text-foreground">{transcript.title}</h2>
          {getStatusBadge()}
        </div>
        <Button onClick={onNewRecording} variant="outline">
          <Mic className="w-4 h-4 mr-2" />
          Neue Aufnahme
        </Button>
      </div>
      <div className="grid grid-cols-3 gap-8">
        <div className="col-span-2">
          <h3 className="text-xl font-semibold text-foreground mb-4">Transkript</h3>
          <div className="prose prose-slate dark:prose-invert max-w-none text-foreground whitespace-pre-wrap leading-relaxed">
            {transcript.transcript}
          </div>
        </div>
        <div className="col-span-1">
          <div className="bg-muted/50 p-6 rounded-lg">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-semibold text-foreground">Zusammenfassung</h3>
              <Button variant="ghost" size="icon">
                <TfiReload />
              </Button>
            </div>
            <div className="prose prose-slate dark:prose-invert max-w-none text-muted-foreground whitespace-pre-wrap">
              {transcript.summary || "Noch keine Zusammenfassung verfügbar"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TranscriptView;
