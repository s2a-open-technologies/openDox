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

import { useTranslation } from "react-i18next";
import { useEffect, useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Mic, Check, Loader2, AlertCircle, Copy, Save, AlertTriangle, Pencil, Eye, Download } from "lucide-react";
import { TfiReload } from "react-icons/tfi";
import type { Recording, Category } from "@/pages/Dashboard";
import { cn } from "@/lib/utils";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth } from "@/contexts/AuthContext";

interface TranscriptViewProps {
  transcript: Recording | null;
  categories: Category[];
  onNewRecording: () => void;
  onSave: (id: string, content: string, summarize: string) => Promise<void>;
  onCategoryChange: (id: string, categoryId: number) => Promise<void>;
}

const TranscriptView = ({ transcript, categories, onNewRecording, onSave, onCategoryChange }: TranscriptViewProps) => {
  const { t } = useTranslation(["transcript", "disclaimer"]);
  const { authFetch } = useAuth();
  const [taskStatus, setTaskStatus] = useState<string | null>(null);
  const [editedContent, setEditedContent] = useState(transcript?.content || "");
  const [editedSummary, setEditedSummary] = useState(transcript?.summarize || "");
  const [confirmed, setConfirmed] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [isEditingSummary, setIsEditingSummary] = useState(false);
  const [regeneratingId, setRegeneratingId] = useState<number | null>(null);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [hasAudio, setHasAudio] = useState<boolean>(!!transcript?.hasAudio);
  const [isChangingCategory, setIsChangingCategory] = useState(false);

  const editedContentRef = useRef(editedContent);
  const editedSummaryRef = useRef(editedSummary);
  editedContentRef.current = editedContent;
  editedSummaryRef.current = editedSummary;

  const currentDbIdRef = useRef(transcript?.dbId);
  currentDbIdRef.current = transcript?.dbId;

  const prevId = useRef(transcript?.id);

  useEffect(() => {
    if (transcript?.id !== prevId.current) {
      setEditedContent(transcript?.content || "");
      setEditedSummary(transcript?.summarize || "");
      setConfirmed(false);
      setHasUnsavedChanges(false);
      setIsEditingSummary(false);
      setConfirmDialogOpen(false);
      setHasAudio(!!transcript?.hasAudio);
      prevId.current = transcript?.id;
    }
  }, [transcript?.id, transcript?.content, transcript?.summarize, transcript?.hasAudio]);

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
        const res = await authFetch(`/api/v1/records/status/${transcript.taskId}`);
        if (res.ok) {
          const data = await res.json();
          setTaskStatus(data.status);

          if (data.status === 'finished' || data.status === 'error') {
            clearInterval(interval);
          }

          if (transcript?.dbId) {
            const recRes = await authFetch(`/api/v1/records/record/${transcript.dbId}`);
            if (recRes.ok) {
              const recData = await recRes.json();
              if (recData.content && recData.content !== editedContentRef.current) {
                setEditedContent(recData.content);
              }
              if (recData.summarize && recData.summarize !== editedSummaryRef.current) {
                setEditedSummary(recData.summarize);
              }
              if (typeof recData.has_audio === "boolean") {
                setHasAudio(recData.has_audio);
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
        <h2 className="text-2xl font-semibold text-foreground mb-2">{t("empty.title")}</h2>
        <p className="text-muted-foreground mb-6">{t("empty.description")}</p>
        <Button onClick={onNewRecording}>
          <Mic className="w-4 h-4 mr-2" />
          {t("empty.start")}
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
      case 'processing_llm':
        // Redundant with the isProcessing banner above the title row —
        // that one already shows a "läuft"/"arbeitet" indicator.
        return null;
      case 'finished':
        return (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-100 text-green-700 border border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-900">
            <Check className="w-3 h-3" />
            <span className="text-xs font-semibold">{t("status.finished")}</span>
          </div>
        );
      case 'error':
        return (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-100 text-red-700 border border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-900">
            <AlertCircle className="w-3 h-3" />
            <span className="text-xs font-semibold">{t("status.error")}</span>
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
      const ok = confirm(t("copy.unsavedConfirm"));
      if (!ok) return;
    }
    try {
      await navigator.clipboard.writeText(text);
      toast.success(t("copy.success"));
    } catch {
      toast.error(t("copy.failed"));
    }
  };

  const isProcessing = taskStatus === 'pending' || taskStatus === 'running' || taskStatus === 'transcribing' || taskStatus === 'processing_llm';

  const handleCategorySelect = async (val: string) => {
    const newCategoryId = parseInt(val);
    if (!transcript || newCategoryId === transcript.categoryId) return;
    setIsChangingCategory(true);
    try {
      await onCategoryChange(transcript.id, newCategoryId);
    } finally {
      setIsChangingCategory(false);
    }
  };

  const handleRegenerateSummary = async () => {
    if (!transcript?.dbId) return;
    const targetId = transcript.dbId;
    const targetTitle = transcript.title;
    setRegeneratingId(targetId);
    try {
      const res = await authFetch(`/api/v1/records/record/${targetId}/summarize`, { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      if (currentDbIdRef.current === targetId) {
        setEditedSummary(data.summarize || "");
        toast.success(t("summary.regenerated"));
      } else {
        toast.success(t("summary.updatedFor", { title: targetTitle }));
      }
    } catch {
      toast.error(t("summary.regenerateFailed"));
    } finally {
      setRegeneratingId(prev => (prev === targetId ? null : prev));
    }
  };

  const handleDownloadAudio = async () => {
    if (!transcript?.dbId) return;
    try {
      const res = await authFetch(`/api/v1/records/record/${transcript.dbId}/audio`);
      if (!res.ok) throw new Error(t("download.failed"));
      const blob = await res.blob();
      const disposition = res.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : `${transcript.title}.mp3`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      toast.error(t("download.failed"));
    }
  };

  return (
    <div className="h-full flex flex-col p-8 gap-6 bg-background">
      {isProcessing && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-muted/80 border border-border animate-pulse">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          <span className="text-sm font-medium text-foreground">
            {taskStatus === 'processing_llm'
              ? t("processing.llm")
              : t("processing.transcribing")}
          </span>
        </div>
      )}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4 flex-wrap">
          <h2 className="text-3xl font-bold text-foreground">{transcript.title}</h2>
          {getStatusBadge()}
          <Select
            value={transcript.categoryId?.toString() || ""}
            onValueChange={handleCategorySelect}
            disabled={isChangingCategory || categories.length === 0}
          >
            <SelectTrigger className="w-auto h-8 text-xs gap-2">
              <SelectValue placeholder={t("categoryPlaceholder")} />
            </SelectTrigger>
            <SelectContent>
              {categories.map((cat) => (
                <SelectItem key={cat.id} value={cat.id.toString()}>{cat.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center justify-between sm:justify-end gap-2">
          {hasAudio && (
            <Button onClick={handleDownloadAudio} variant="outline">
              <Download className="w-4 h-4 mr-2" />
              {t("audio")}
            </Button>
          )}
          <Button onClick={handleSave} disabled={!hasUnsavedChanges || isSaving} variant="outline">
            {isSaving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
            {isSaving ? t("saving") : t("save")}
          </Button>
          <Button onClick={onNewRecording} variant="outline">
            <Mic className="w-4 h-4 mr-2" />
            {t("newRecording")}
          </Button>
        </div>
      </div>

      {hasUnsavedChanges && (
        <div className="text-amber-600 text-sm font-medium flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          {t("unsaved")}
        </div>
      )}

      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="flex flex-col min-h-0">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xl font-semibold text-foreground">{t("title")}</h3>
            <Button
              variant="ghost"
              size="sm"
              disabled={!confirmed}
              onClick={() => handleCopy(editedContent)}
              title={!confirmed ? t("confirmFirst") : ""}
            >
              <Copy className="w-4 h-4 mr-2" />
              {t("copy")}
            </Button>
          </div>
          <Textarea
            value={editedContent}
            onChange={(e) => setEditedContent(e.target.value)}
            placeholder={t("placeholder")}
            readOnly={!confirmed}
            onContextMenu={(e) => { if (!confirmed) e.preventDefault(); }}
            onCopy={(e) => { if (!confirmed) e.preventDefault(); }}
            onCut={(e) => { if (!confirmed) e.preventDefault(); }}
            title={!confirmed ? t("confirmFirst") : undefined}
            className={`flex-1 min-h-0 font-sans shadow-md text-base leading-relaxed resize-none${!confirmed ? ' select-none cursor-not-allowed opacity-75' : ''}`}
          />
        </div>

        <div className="flex flex-col min-h-0">
          <Card className="p-6 flex flex-col flex-1 min-h-0 shadow-md">
            <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
              <h3 className="text-xl font-semibold text-foreground">{t("summary.title")}</h3>
              <div className="flex items-center gap-2 ml-auto">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={!confirmed}
                  onClick={() => handleCopy(editedSummary)}
                  title={!confirmed ? t("confirmFirst") : ""}
                  aria-label={t("summary.copyLabel")}
                >
                  <Copy className="w-4 h-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleRegenerateSummary}
                  disabled={regeneratingId === transcript?.dbId || isProcessing}
                  title={t("summary.regenerate")}
                >
                  {regeneratingId === transcript?.dbId
                    ? <Loader2 className="w-4 h-4 animate-spin" />
                    : <TfiReload />}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={!confirmed}
                  onClick={() => setIsEditingSummary(!isEditingSummary)}
                  title={!confirmed ? t("confirmFirst") : isEditingSummary ? t("markdownPreview") : t("edit")}
                >
                  {isEditingSummary ? <Eye className="w-4 h-4 sm:mr-2" /> : <Pencil className="w-4 h-4 sm:mr-2" />}
                  <span className="hidden sm:inline">{isEditingSummary ? t("preview") : t("edit")}</span>
                </Button>
              </div>
            </div>
            {isEditingSummary ? (
              <Textarea
                value={editedSummary}
                onChange={(e) => setEditedSummary(e.target.value)}
                placeholder={t("summary.none")}
                readOnly={!confirmed}
                onContextMenu={(e) => { if (!confirmed) e.preventDefault(); }}
                onCopy={(e) => { if (!confirmed) e.preventDefault(); }}
                onCut={(e) => { if (!confirmed) e.preventDefault(); }}
                title={!confirmed ? t("confirmFirst") : undefined}
                className={`flex-1 min-h-0 font-sans shadow-xs text-base leading-relaxed resize-none${!confirmed ? ' select-none cursor-not-allowed opacity-75' : ''}`}
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
                  <p className="text-muted-foreground italic">{t("summary.none")}</p>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>


      <Alert variant="destructive" className="mt-4! shadow-md">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>{t("disclaimer:title")}</AlertTitle>
        <AlertDescription className="text-sm leading-relaxed">
          {t("disclaimer:view")}
        </AlertDescription>
      </Alert>


      <div className="border-t pt-4 mt-4">
        <div className="flex items-start gap-3">
          <Checkbox
            id="transcript-confirm"
            checked={confirmed}
            onCheckedChange={(checked) => {
              if (checked && !confirmed) {
                setConfirmDialogOpen(true);
              } else {
                setConfirmed(false);
              }
            }}
            className="mt-0.5"
          />
          <label htmlFor="transcript-confirm" className="text-sm text-muted-foreground cursor-pointer">
            {t("confirmLabel")}
          </label>
        </div>
      </div>

      <Dialog open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("dialog.title")}</DialogTitle>
            <DialogDescription>
              {t("dialog.description")}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDialogOpen(false)}>
              {t("dialog.cancel")}
            </Button>
            <Button onClick={() => {
              setConfirmed(true);
              setConfirmDialogOpen(false);
            }}>
              {t("dialog.confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TranscriptView;
