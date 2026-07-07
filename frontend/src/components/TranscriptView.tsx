/*
  openDox - Medical transcription platform
  Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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

import { useEffect, useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Mic, Check, Loader2, AlertCircle, Copy, Save, AlertTriangle, Pencil, Eye } from "lucide-react";
import { TfiReload } from "react-icons/tfi";
import type { Recording } from "@/pages/Dashboard";
import { cn } from "@/lib/utils";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface TranscriptViewProps {
  transcript: Recording | null;
  onNewRecording: () => void;
  onSave: (id: string, content: string, summarize: string) => Promise<void>;
}

const TranscriptView = ({ transcript, onNewRecording, onSave }: TranscriptViewProps) => {
  const [taskStatus, setTaskStatus] = useState<string | null>(null);
  const [editedContent, setEditedContent] = useState(transcript?.content || "");
  const [editedSummary, setEditedSummary] = useState(transcript?.summarize || "");
  const [confirmed, setConfirmed] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [isEditingSummary, setIsEditingSummary] = useState(false);
  const [isRegeneratingSummary, setIsRegeneratingSummary] = useState(false);

  const editedContentRef = useRef(editedContent);
  const editedSummaryRef = useRef(editedSummary);
  editedContentRef.current = editedContent;
  editedSummaryRef.current = editedSummary;

  const prevId = useRef(transcript?.id);

  useEffect(() => {
    if (transcript?.id !== prevId.current) {
      setEditedContent(transcript?.content || "");
      setEditedSummary(transcript?.summarize || "");
      setConfirmed(false);
      setHasUnsavedChanges(false);
      setIsEditingSummary(false);
      prevId.current = transcript?.id;
    }
  }, [transcript?.id, transcript?.content, transcript?.summarize]);

  useEffect(() => {
    const contentDiff = (transcript?.content || "") !== editedContent;
    const summaryDiff = (transcript?.summarize || "") !== editedSummary;
    setHasUnsavedChanges(contentDiff || summaryDiff);
  }, [editedContent, editedSummary, transcript?.content, transcript?.summarize]);

  useEffect(() => {
    if (!transcript?.taskId) {
      setTaskStatus(null);
      return;
    }

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

          if (transcript?.dbId) {
            const recRes = await fetch(`/api/v1/records/record/${transcript.dbId}`);
            if (recRes.ok) {
              const recData = await recRes.json();
              if (recData.content && recData.content !== editedContentRef.current) {
                setEditedContent(recData.content);
              }
              if (recData.summarize && recData.summarize !== editedSummaryRef.current) {
                setEditedSummary(recData.summarize);
              }
            }
          }
        }
      } catch (e) {
        console.error("Status check failed", e);
      }
    }
    checkStatus();
    const interval: ReturnType<typeof setInterval> = setInterval(checkStatus, 2000);
    return () => clearInterval(interval);
  }, [transcript?.taskId, transcript?.dbId]);

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
      case 'pending':
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

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave(transcript.id, editedContent, editedSummary);
      setHasUnsavedChanges(false);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCopy = async (text: string) => {
    if (hasUnsavedChanges) {
      const ok = confirm('Es gibt ungespeicherte Änderungen. Trotzdem kopieren?');
      if (!ok) return;
    }
    try {
      await navigator.clipboard.writeText(text);
      toast.success('In die Zwischenablage kopiert');
    } catch {
      toast.error('Kopieren fehlgeschlagen');
    }
  };

  const isProcessing = taskStatus === 'pending' || taskStatus === 'running' || taskStatus === 'transcribing' || taskStatus === 'processing_llm';

  const handleRegenerateSummary = async () => {
    if (!transcript?.dbId) return;
    setIsRegeneratingSummary(true);
    try {
      const res = await fetch(`/api/v1/records/record/${transcript.dbId}/summarize`, { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setEditedSummary(data.summarize || "");
      toast.success('Zusammenfassung neu generiert');
    } catch {
      toast.error('Fehler beim Generieren der Zusammenfassung');
    } finally {
      setIsRegeneratingSummary(false);
    }
  };

  return (
    <div className="h-full flex flex-col p-8 gap-6 bg-background">
      {isProcessing && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-muted/80 border border-border animate-pulse">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          <span className="text-sm font-medium text-foreground">
            {taskStatus === 'processing_llm'
              ? 'KI erstellt Zusammenfassung...'
              : 'Transkription läuft...'}
          </span>
        </div>
      )}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-3xl font-bold text-foreground">{transcript.title}</h2>
          {getStatusBadge()}
        </div>
        <div className="flex items-center justify-between sm:justify-end gap-2">
          <Button onClick={handleSave} disabled={!hasUnsavedChanges || isSaving} variant="outline">
            {isSaving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
            {isSaving ? "Speichere..." : "Speichern"}
          </Button>
          <Button onClick={onNewRecording} variant="outline">
            <Mic className="w-4 h-4 mr-2" />
            Neue Aufnahme
          </Button>
        </div>
      </div>

      {hasUnsavedChanges && (
        <div className="text-amber-600 text-sm font-medium flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          Ungespeicherte Änderungen vorhanden
        </div>
      )}

      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="flex flex-col min-h-0">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xl font-semibold text-foreground">Transkript</h3>
            <Button
              variant="ghost"
              size="sm"
              disabled={!confirmed}
              onClick={() => handleCopy(editedContent)}
              title={!confirmed ? "Bitte zuerst Bestätigungshaken setzen" : ""}
            >
              <Copy className="w-4 h-4 mr-2" />
              Kopieren
            </Button>
          </div>
          <Textarea
            value={editedContent}
            onChange={(e) => setEditedContent(e.target.value)}
            placeholder="Transkript..."
            readOnly={!confirmed}
            onContextMenu={(e) => { if (!confirmed) e.preventDefault(); }}
            onCopy={(e) => { if (!confirmed) e.preventDefault(); }}
            onCut={(e) => { if (!confirmed) e.preventDefault(); }}
            title={!confirmed ? 'Bitte zuerst Bestätigungshaken setzen' : undefined}
            className={`flex-1 min-h-0 font-sans text-base leading-relaxed resize-none${!confirmed ? ' select-none cursor-not-allowed opacity-75' : ''}`}
          />
        </div>

        <div className="flex flex-col min-h-0">
          <div className="bg-muted/50 p-6 rounded-lg flex flex-col flex-1 min-h-0">
            <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
              <h3 className="text-xl font-semibold text-foreground">Zusammenfassung</h3>
              <div className="flex items-center gap-2 ml-auto">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={!confirmed}
                  onClick={() => handleCopy(editedSummary)}
                  title={!confirmed ? "Bitte zuerst Bestätigungshaken setzen" : ""}
                >
                  <Copy className="w-4 h-4 mr-2" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleRegenerateSummary}
                  disabled={isRegeneratingSummary || isProcessing}
                  title="Zusammenfassung neu generieren"
                >
                  {isRegeneratingSummary
                    ? <Loader2 className="w-4 h-4 animate-spin" />
                    : <TfiReload />}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={!confirmed}
                  onClick={() => setIsEditingSummary(!isEditingSummary)}
                  title={!confirmed ? "Bitte zuerst Bestätigungshaken setzen" : isEditingSummary ? "Markdown-Vorschau" : "Bearbeiten"}
                >
                  {isEditingSummary ? <Eye className="w-4 h-4 sm:mr-2" /> : <Pencil className="w-4 h-4 sm:mr-2" />}
                  <span className="hidden sm:inline">{isEditingSummary ? "Vorschau" : "Bearbeiten"}</span>
                </Button>
              </div>
            </div>
            {isEditingSummary ? (
              <Textarea
                value={editedSummary}
                onChange={(e) => setEditedSummary(e.target.value)}
                placeholder="Noch keine Zusammenfassung verfügbar"
                readOnly={!confirmed}
                onContextMenu={(e) => { if (!confirmed) e.preventDefault(); }}
                onCopy={(e) => { if (!confirmed) e.preventDefault(); }}
                onCut={(e) => { if (!confirmed) e.preventDefault(); }}
                title={!confirmed ? 'Bitte zuerst Bestätigungshaken setzen' : undefined}
                className={`flex-1 min-h-0 font-sans text-base leading-relaxed resize-none${!confirmed ? ' select-none cursor-not-allowed opacity-75' : ''}`}
              />
            ) : (
              <div
                onContextMenu={(e) => { if (!confirmed) e.preventDefault(); }}
                onCopy={(e) => { if (!confirmed) e.preventDefault(); }}
                className={`flex-1 min-h-0 overflow-y-auto prose prose-sm dark:prose-invert max-w-none${!confirmed ? ' select-none pointer-events-none opacity-75' : ''}`}
              >
                {editedSummary ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{editedSummary}</ReactMarkdown>
                ) : (
                  <p className="text-muted-foreground italic">Noch keine Zusammenfassung verfügbar</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>


      <Alert variant="destructive" className="!mt-4">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Kein Medizinprodukt</AlertTitle>
        <AlertDescription className="text-sm leading-relaxed">
          Dieses Tool ist kein Medizinprodukt gemäß Medizinproduktegesetz (MPG). Es dient ausschließlich der Unterstützung bei der Dokumentation.
          Alle maschinell erstellten Transkriptionen und Zusammenfassungen müssen von qualifiziertem Fachpersonal überprüft werden.
          Es ersetzt keine ärztliche Diagnose, Beratung oder Therapieempfehlung.
        </AlertDescription>
      </Alert>


      <div className="border-t pt-4 mt-4">
        <div className="flex items-start gap-3">
          <Checkbox
            id="transcript-confirm"
            checked={confirmed}
            onCheckedChange={(checked) => setConfirmed(checked === true)}
            className="mt-0.5"
          />
          <label htmlFor="transcript-confirm" className="text-sm text-muted-foreground cursor-pointer">
            Ich habe den Text sorgfältig überprüft und ggf. korrigiert. Ich übernehme die Verantwortung für den kopierten Inhalt.
          </label>
        </div>
      </div>
    </div>
  );
};

export default TranscriptView;
