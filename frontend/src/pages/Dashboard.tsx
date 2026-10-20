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

import { apiErrorMessage } from '@/lib/apiError';
import { useTranslation } from "react-i18next";
import { useState, useEffect, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import Recorder, { RecorderHandle, RecordingStartData } from "@/components/Recorder";
import TranscriptView from "@/components/TranscriptView";
import ArchiveDayList from "@/components/ArchiveDayList";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { AlertTriangle, Radio, Menu } from "lucide-react";
import { Logo } from "@/components/Logo";
import { useAuth } from "@/contexts/AuthContext";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogClose,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { defaultCategoryId } from "@/lib/categories";

export interface Recording {
  id: string;
  dbId?: number;
  title: string;
  categoryId: number | null;
  categoryName: string;
  timestamp: string;
  content: string;
  summarize: string;
  userid: string;
  taskId?: string | number;
  hasAudio?: boolean;
}

export interface Category {
  id: number;
  name: string;
}

interface RecordData {
  id: number;
  session_id: string;
  user_id: number;
  category_id: number | null;
  title: string;
  content: string | null;
  summarize: string | null;
  timestamp: string;
  task_id?: number | null;
  has_audio?: boolean;
}

const Dashboard = () => {
  const { t, i18n } = useTranslation(["dashboard", "disclaimer"]);
  const { user, authFetch } = useAuth();
  const recorderRef = useRef<RecorderHandle>(null);
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [selectedRecording, setSelectedRecording] = useState<Recording | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newCategoryName, setNewCategoryName] = useState("");
  const [categoryId, setCategoryId] = useState<string | null>(null);
  // activeSessionId: whether the Recorder view is shown (record mode).
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  // unfinishedSessionId: server-tracked unfinished recording -> drives the sidebar badge.
  const [unfinishedSessionId, setUnfinishedSessionId] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  // Archive overview: selected day key (YYYY-MM-DD or "unknown") in archive mode.
  const [selectedArchiveDate, setSelectedArchiveDate] = useState<string | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // Upload dialog state
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadCategoryId, setUploadCategoryId] = useState<string | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const userId = user?.id?.toString() || "";

  // Mode switch between Library and Archive. Leaves recorder mode if active and
  // clears any selection so a transcript from one mode never leaks into the other.
  const handleToggleArchived = (show: boolean) => {
    setShowArchived(show);
    setSelectedArchiveDate(null);
    if (selectedRecording) setSelectedRecording(null);
    if (activeSessionId) setActiveSessionId(null);
  };

  const fetchRecords = async () => {
    try {
      const response = await authFetch(`/api/v1/records/list-records/${userId}?archived=${showArchived}`);
      if (response.ok) {
        const data = await response.json();
        setRecordings(data.map((d: RecordData) => ({
          id: d.session_id || d.id.toString(),
          dbId: d.id,
          title: d.title,
          categoryId: d.category_id,
          categoryName: "",
          timestamp: d.timestamp,
          content: d.content || "",
          summarize: d.summarize || "",
          userid: d.user_id.toString(),
          taskId: d.task_id || undefined,
          hasAudio: d.has_audio || false,
        })));
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchCategories = async () => {
    try {
      const res = await authFetch('/api/v1/settings/categories/');
      if (res.ok) {
        const data = await res.json();
        setCategories(data);
        setCategoryId(prev => prev ?? defaultCategoryId(data));
      }
    } catch (err) {
      console.error('Failed to fetch categories:', err);
    }
  };

  useEffect(() => {
    if (!userId) return;
    fetchRecords();
    fetchCategories();
  }, [userId, showArchived]);

  // Separate effect: active-session only needs to re-run on login/user change,
  // not on every Library↔Archive tab toggle. Avoids race where the response
  // arrives with {active: false} while a recording is being started.
  useEffect(() => {
    if (!userId) return;
    authFetch(`/api/v1/records/active-session/${userId}`)
      .then((res) => res.json())
      .then((data) => {
        if (data?.active) {
          setUnfinishedSessionId(data.session_id);
        } else {
          setUnfinishedSessionId(null);
        }
      })
      .catch(() => setUnfinishedSessionId(null));
  }, [userId]);

  const handleDelete = async (id: string) => {
    const rec = recordings.find(r => r.id === id);
    if (!rec?.dbId) return;
    try {
      if (!confirm(t("confirmDelete"))) return;
      const response = await authFetch(`/api/v1/records/record/${rec.dbId}`, { method: "DELETE" });
      if (!response.ok) throw new Error(t("deleteFailedShort"));
      toast.success(t("deleted"));
      if (selectedRecording?.id === id) setSelectedRecording(null);
      fetchRecords();
    } catch (error) {
      console.error(error);
      toast.error(t("deleteFailed"));
    }
  };

  const handleArchive = async (id: string) => {
    const rec = recordings.find(r => r.id === id);
    if (!rec?.dbId) return;
    try {
      const response = await authFetch(`/api/v1/records/record/${rec.dbId}/archive`, { method: "PUT" });
      if (!response.ok) throw new Error(t("archiveFailedShort"));
      toast.success(t("archived"));
      if (selectedRecording?.id === id) setSelectedRecording(null);
      fetchRecords();
    } catch (error) {
      console.error(error);
      toast.error(t("archiveFailedShort"));
    }
  };

  const handleUnarchive = async (id: string) => {
    const rec = recordings.find(r => r.id === id);
    if (!rec?.dbId) return;
    try {
      const response = await authFetch(`/api/v1/records/record/${rec.dbId}/unarchive`, { method: "PUT" });
      if (!response.ok) throw new Error(t("restoreFailed"));
      toast.success(t("restored"));
      if (selectedRecording?.id === id) setSelectedRecording(null);
      fetchRecords();
    } catch (error) {
      console.error(error);
      toast.error(t("restoreFailed"));
    }
  };

  const handleRecordingStart = (recordingData: RecordingStartData) => {
    setActiveSessionId(recordingData.session_id);
    setUnfinishedSessionId(recordingData.session_id);
    const cat = categories.find(c => c.id.toString() === categoryId);
    const tempRecording: Recording = {
      id: recordingData.session_id,
      dbId: recordingData.id,
      title: newTitle || recordingData.title || t("defaultTitle", { n: recordings.length + 1 }),
      categoryId: categoryId ? parseInt(categoryId) : null,
      categoryName: cat?.name || newCategoryName || t("uncategorized"),
      timestamp: new Date().toLocaleString("de-DE"),
      content: "",
      summarize: "",
      userid: userId,
      taskId: undefined,
    };
    if (showArchived) setShowArchived(false);
    setRecordings(prev => [tempRecording, ...prev]);
    // Don't set selectedRecording here: the Recorder view is active and setting
    // it would cause TranscriptView to appear after "Zur Übersicht", hiding the
    // welcome screen and the "Fortsetzen" banner.
  };

  const handleFinalTranscription = async (sessionId: string, taskId?: string | number) => {
    // Recording stopped -> workflow takes over; the unfinished session is cleared.
    setActiveSessionId(null);
    setUnfinishedSessionId(null);
    try {
      const res = await authFetch(`/api/v1/records/by-session/${sessionId}`);
      if (!res.ok) throw new Error("Failed to fetch final record");
      const data = await res.json();

      const effectiveTaskId = taskId || data.task_id || undefined;

      if (effectiveTaskId) {
        setRecordings(prev => prev.map(r => r.id === sessionId ? { ...r, taskId: effectiveTaskId } : r));
      }

      const finalRecording: Recording = {
        id: data.session_id,
        dbId: data.id,
        title: data.title,
        categoryId: data.category_id,
        categoryName: categories.find(c => c.id === data.category_id)?.name || t("uncategorized"),
        timestamp: data.timestamp,
        content: data.content || "",
        summarize: data.summarize || "",
        userid: data.user_id.toString(),
        taskId: effectiveTaskId,
      };

      setRecordings(prev => prev.map(r => r.id === sessionId ? finalRecording : r));
      setSelectedRecording(finalRecording);
    } catch (err) {
      console.error(err);
      toast.error(t("fetchFailed"));
    }
  };

  const handleSelectRecording = async (recording: Recording) => {
    // Clicking the unfinished recording -> (re)enter record mode and resume it.
    if (unfinishedSessionId && recording.id === unfinishedSessionId) {
      setSelectedRecording(null);
      setActiveSessionId(unfinishedSessionId);
      return;
    }
    // Clicking another recording while in record mode -> just leave the recorder
    // view. The session stays unfinished in the store (badge persists).
    if (activeSessionId) {
      setActiveSessionId(null);
    }
    try {
      if (!recording.dbId) {
        setSelectedRecording(recording);
        return;
      }
      const result = await authFetch(`/api/v1/records/record/${recording.dbId}`);
      if (!result.ok) throw new Error("Failed to fetch record");
      const data = await result.json();
      setSelectedRecording({
        id: data.session_id,
        dbId: data.id,
        title: data.title,
        categoryId: data.category_id,
        categoryName: categories.find(c => c.id === data.category_id)?.name || t("uncategorized"),
        timestamp: data.timestamp,
        content: data.content || "",
        summarize: data.summarize || "",
        userid: data.user_id.toString(),
        taskId: data.task_id || recording.taskId,
      });
    } catch (err) {
      console.error(err);
      toast.error(t("loadFailed"));
    }
  };

  const handleSaveRecording = async (id: string, content: string, summarize: string) => {
    const rec = recordings.find(r => r.id === id);
    if (!rec?.dbId) return;
    try {
      const res = await authFetch(`/api/v1/records/record/${rec.dbId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, summarize }),
      });
      if (!res.ok) throw new Error("Failed to save");
      toast.success(t("saved"));
      setRecordings(prev => prev.map(r => r.id === id ? { ...r, content, summarize } : r));
      if (selectedRecording?.id === id) {
        setSelectedRecording(prev => prev ? { ...prev, content, summarize } : null);
      }
    } catch (err) {
      console.error(err);
      toast.error(t("saveFailed"));
    }
  };

  const handleCategoryChange = async (id: string, newCategoryId: number) => {
    const rec = recordings.find(r => r.id === id);
    if (!rec?.dbId) return;
    try {
      const res = await authFetch(`/api/v1/records/record/${rec.dbId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category_id: newCategoryId }),
      });
      if (!res.ok) throw new Error("Failed to change category");
      const categoryName = categories.find(c => c.id === newCategoryId)?.name || t("uncategorized");
      toast.success(t("categoryChanged"));
      setRecordings(prev => prev.map(r => r.id === id ? { ...r, categoryId: newCategoryId, categoryName } : r));
      if (selectedRecording?.id === id) {
        setSelectedRecording(prev => prev ? { ...prev, categoryId: newCategoryId, categoryName } : null);
      }
    } catch (err) {
      console.error(err);
      toast.error(t("categoryChangeFailed"));
    }
  };

  const handleStartRecordingSession = async () => {
    // Only one active session per user. If an unfinished one exists, cancel it first.
    if (unfinishedSessionId) {
      const ok = confirm(
        "Es gibt bereits eine unfertige Aufnahme. Diese wird verworfen, wenn Sie eine neue starten. Fortfahren?"
      );
      if (!ok) return;
      try {
        await authFetch(`/api/v1/records/cancel-session/${userId}`, { method: "DELETE" });
      } catch (err) {
        console.error(err);
      }
      setUnfinishedSessionId(null);
    }
    if (!newTitle.trim()) setNewTitle(t("defaultTitle", { n: recordings.length + 1 }));
    if (!newCategoryName.trim()) setNewCategoryName(t("uncategorized"));
    setIsDialogOpen(false);
    setTimeout(() => {
      if (showArchived) setShowArchived(false);
      else fetchRecords();
      setActiveSessionId("new");
    }, 300);
  };

  const handleUploadSubmit = async () => {
    if (!uploadFile || !uploadCategoryId || !userId) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("category_id", uploadCategoryId);
      formData.append("user_id", userId);
      if (uploadTitle.trim()) formData.append("title", uploadTitle.trim());

      const res = await authFetch("/api/v1/records/upload", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: t("upload.failed") }));
        toast.error(apiErrorMessage(err, t("upload.failed")));
        return;
      }
      const data = await res.json();

      const cat = categories.find(c => c.id.toString() === uploadCategoryId);
      const tempRecording: Recording = {
        id: data.session_id,
        dbId: data.record_id,
        title: uploadTitle.trim() || t("upload.defaultTitle", { date: new Date().toLocaleString(i18n.language) }),
        categoryId: parseInt(uploadCategoryId),
        categoryName: cat?.name || t("uncategorized"),
        timestamp: new Date().toLocaleString("de-DE"),
        content: "",
        summarize: "",
        userid: userId,
        taskId: data.task_id,
      };
      if (showArchived) setShowArchived(false);
      setRecordings(prev => [tempRecording, ...prev]);
      setSelectedRecording(tempRecording);
      setUploadDialogOpen(false);
      setUploadFile(null);
      setUploadTitle("");
      setUploadCategoryId(null);
      toast.success(t("upload.success"));
    } catch (err) {
      console.error(err);
      toast.error(t("upload.failed"));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="relative min-h-dvh bg-background flex">
      <Sidebar
        recordings={recordings}
        onSelectRecording={handleSelectRecording}
        selectedId={selectedRecording?.id}
        activeSessionId={unfinishedSessionId || undefined}
        onDeleteRecording={handleDelete}
        onArchiveRecording={handleArchive}
        onUnarchiveRecording={handleUnarchive}
        showArchived={showArchived}
        onToggleArchived={handleToggleArchived}
        selectedArchiveDate={selectedArchiveDate}
        onSelectArchiveDate={(dateKey) => {
          setSelectedArchiveDate(dateKey);
          if (selectedRecording) setSelectedRecording(null);
        }}
        onUploadClick={() => {
          setUploadCategoryId(prev => prev ?? defaultCategoryId(categories));
          setUploadDialogOpen(true);
        }}
        showUploadButton={!activeSessionId && !selectedRecording}
        mobileOpen={mobileSidebarOpen}
        onMobileOpenChange={setMobileSidebarOpen}
      />
      <main className="flex-1 min-w-0 overflow-auto bg-muted/30 flex flex-col">
        <div className="md:hidden relative flex items-center justify-center px-3 py-2 border-b border-border bg-background/95 backdrop-blur-sm supports-backdrop-filter:bg-background/60 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            className="absolute left-3"
            onClick={() => setMobileSidebarOpen(true)}
          >
            <Menu className="w-5 h-5" />
            <span className="sr-only">{t("openMenu")}</span>
          </Button>
          <Logo className="h-8" />
        </div>
        <div className="flex-1 min-h-0 overflow-auto">
        {activeSessionId ? (
          <div className="flex flex-col items-center justify-center h-full">
            <Recorder
              ref={recorderRef}
              userId={userId}
              title={newTitle}
              categoryId={categoryId}
              resumeSessionId={activeSessionId !== "new" ? activeSessionId ?? undefined : undefined}
              onRecordingStart={handleRecordingStart}
              onFinalTranscription={handleFinalTranscription}
              autoStart={true}
            />
            <div className="flex items-center gap-2 mt-4">
              <Button
                variant="ghost"
                onClick={async () => {
                  const ok = confirm(t("cancelConfirm"));
                  if (!ok) return;
                  // Wait for pending chunk uploads before cancelling on the server,
                  // so in-flight uploads don't create orphaned files after cleanup.
                  try { await recorderRef.current?.waitForUploads(); } catch { /* nothing to wait for */ }
                  setActiveSessionId(null);
                  setUnfinishedSessionId(null);
                  setSelectedRecording(null);
                  try {
                    await authFetch(`/api/v1/records/cancel-session/${userId}`, { method: "DELETE" });
                  } catch (err) {
                    console.error(err);
                    toast.error(t("cancelFailed"));
                  }
                  fetchRecords();
                }}
              >
                {t("cancel")}
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setActiveSessionId(null);
                  // Clear selected so the welcome screen is shown (not an empty TranscriptView).
                  // Badge stays visible in sidebar via unfinishedSessionId.
                  setSelectedRecording(null);
                }}
              >
                {t("toOverview")}
              </Button>
            </div>
          </div>
        ) : showArchived ? (
          selectedRecording ? (
            <TranscriptView
              transcript={selectedRecording}
              categories={categories}
              onNewRecording={async () => {
                setSelectedRecording(null);
                await fetchRecords();
              }}
              onSave={handleSaveRecording}
              onCategoryChange={handleCategoryChange}
            />
          ) : (
            <ArchiveDayList
              recordings={recordings}
              selectedDate={selectedArchiveDate}
              onSelectRecording={handleSelectRecording}
              onUnarchiveRecording={handleUnarchive}
              onDeleteRecording={handleDelete}
              onBackToDates={() => {
                setSelectedArchiveDate(null);
                setSelectedRecording(null);
              }}
            />
          )
        ) : !selectedRecording ? (
          <div className="flex flex-col items-center justify-center h-full space-y-4 text-center">
            {unfinishedSessionId && (
              <div className="w-full max-w-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-4 flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/40 flex items-center justify-center shrink-0">
                  <Radio className="w-5 h-5 text-red-500 animate-pulse" />
                </div>
                <div className="flex-1 text-left">
                  <p className="text-sm font-semibold text-red-700 dark:text-red-400">{t("unfinished.title")}</p>
                  <p className="text-xs text-red-600/70 dark:text-red-400/70">{t("unfinished.description")}</p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button
                    size="sm"
                    onClick={() => setActiveSessionId(unfinishedSessionId)}
                  >
                    {t("unfinished.resume")}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-red-600 hover:text-red-700 hover:bg-red-100 dark:hover:bg-red-900/30"
                    onClick={async () => {
                      const ok = confirm(t("unfinished.discardConfirm"));
                      if (!ok) return;
                      try {
                        await authFetch(`/api/v1/records/cancel-session/${userId}`, { method: "DELETE" });
                      } catch (err) {
                        console.error(err);
                      }
                      setUnfinishedSessionId(null);
                      fetchRecords();
                    }}
                  >
                    {t("unfinished.discard")}
                  </Button>
                </div>
              </div>
            )}

            <div className="space-y-2">
              <h1 className="text-3xl font-bold">{t("welcome.title")}</h1>
              <p className="text-muted-foreground">{t("welcome.description")}</p>
            </div>

            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button size="lg">{t("new.start")}</Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                  <DialogTitle>{t("new.title")}</DialogTitle>
                  <DialogDescription>
                    {t("new.description")}
                  </DialogDescription>
                </DialogHeader>

                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <label htmlFor="title" className="text-sm font-medium">{t("new.titleLabel")}</label>
                    <Input
                      id="title"
                      value={newTitle}
                      onChange={(e) => setNewTitle(e.target.value)}
                      placeholder={t("new.titlePlaceholder")}
                      autoFocus
                    />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm font-medium">{t("category")}</label>
                    <Select value={categoryId || ""} onValueChange={(val) => {
                      setCategoryId(val);
                      const cat = categories.find(c => c.id.toString() === val);
                      setNewCategoryName(cat?.name || "");
                    }}>
                      <SelectTrigger>
                        <SelectValue placeholder={t("categoryPlaceholder")} />
                      </SelectTrigger>
                      <SelectContent>
                        {categories.map((cat) => (
                          <SelectItem key={cat.id} value={cat.id.toString()}>{cat.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {categories.length === 0 && (
                      <p className="text-xs text-muted-foreground">
                        {t("categoriesHint")}
                      </p>
                    )}
                  </div>

                  <Alert variant="destructive" className="mt-2">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertTitle>{t("disclaimer:noticeTitle")}</AlertTitle>
                    <AlertDescription className="text-sm leading-relaxed">
                      {t("disclaimer:view")}
                    </AlertDescription>
                  </Alert>
                </div>

                <DialogFooter>
                  <DialogClose asChild>
                    <Button type="button" variant="secondary">{t("cancel")}</Button>
                  </DialogClose>
                  <Button
                    onClick={handleStartRecordingSession}
                    disabled={!categoryId}
                  >
                    {t("new.submit")}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        ) : (
          <TranscriptView
            transcript={selectedRecording}
            categories={categories}
            onNewRecording={async () => {
              setSelectedRecording(null);
              setCategoryId(defaultCategoryId(categories));
              setNewTitle("");
              setNewCategoryName("");
              await fetchRecords();
            }}
            onSave={handleSaveRecording}
            onCategoryChange={handleCategoryChange}
          />
        )}
        </div>

        <Dialog open={uploadDialogOpen} onOpenChange={(open) => {
          if (!uploading) setUploadDialogOpen(open);
        }}>
          <DialogContent className="sm:max-w-[600px]">
            <DialogHeader>
              <DialogTitle>{t("upload.title")}</DialogTitle>
              <DialogDescription>
                {t("upload.description")}
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <label htmlFor="upload-title" className="text-sm font-medium">{t("upload.titleOptional")}</label>
                <Input
                  id="upload-title"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder={t("upload.titlePlaceholder")}
                  disabled={uploading}
                />
              </div>
              <div className="grid gap-2">
                <label className="text-sm font-medium">{t("category")}</label>
                <Select
                  value={uploadCategoryId || ""}
                  onValueChange={(val) => setUploadCategoryId(val)}
                  disabled={uploading}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t("categoryPlaceholder")} />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((cat) => (
                      <SelectItem key={cat.id} value={cat.id.toString()}>{cat.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {categories.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    {t("categoriesHint")}
                  </p>
                )}
              </div>
              <div className="grid gap-2">
                <label htmlFor="upload-file" className="text-sm font-medium">{t("upload.file")}</label>
                <Input
                  id="upload-file"
                  type="file"
                  accept="audio/*"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  disabled={uploading}
                />
                {uploadFile && (
                  <p className="text-xs text-muted-foreground truncate">
                    {t("upload.selected", { name: uploadFile.name })}
                  </p>
                )}
              </div>

              <Alert variant="destructive" className="mt-2">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>{t("disclaimer:noticeTitle")}</AlertTitle>
                <AlertDescription className="text-sm leading-relaxed">
                  {t("disclaimer:view")}
                </AlertDescription>
              </Alert>
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="secondary" disabled={uploading}>{t("cancel")}</Button>
              </DialogClose>
              <Button
                onClick={handleUploadSubmit}
                disabled={!uploadCategoryId || !uploadFile || uploading}
              >
                {uploading ? t("upload.uploading") : t("upload.submit")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
};

export default Dashboard;
