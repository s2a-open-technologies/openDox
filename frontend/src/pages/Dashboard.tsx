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

import { useState, useEffect, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import Recorder, { RecorderHandle } from "@/components/Recorder";
import TranscriptView from "@/components/TranscriptView";
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
}

interface Category {
  id: number;
  name: string;
}

const Dashboard = () => {
  const { user } = useAuth();
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
  const [categories, setCategories] = useState<Category[]>([]);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const userId = user?.id?.toString() || "";

  const fetchRecords = async () => {
    try {
      const response = await fetch(`/api/v1/records/list-records/${userId}?archived=${showArchived}`);
      if (response.ok) {
        const data = await response.json();
        setRecordings(data.map((d: any) => ({
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
        })));
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchCategories = async () => {
    try {
      const res = await fetch('/api/v1/settings/categories/');
      if (res.ok) {
        const data = await res.json();
        setCategories(data);
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
    fetch(`/api/v1/records/active-session/${userId}`)
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
      if (!confirm("Möchten Sie diese Aufnahme wirklich unwiderruflich löschen?")) return;
      const response = await fetch(`/api/v1/records/record/${rec.dbId}`, { method: "DELETE" });
      if (!response.ok) throw new Error("Fehler beim Löschen");
      toast.success("Aufnahme gelöscht");
      if (selectedRecording?.id === id) setSelectedRecording(null);
      fetchRecords();
    } catch (error) {
      console.error(error);
      toast.error("Fehler beim Löschen der Aufnahme");
    }
  };

  const handleArchive = async (id: string) => {
    const rec = recordings.find(r => r.id === id);
    if (!rec?.dbId) return;
    try {
      const response = await fetch(`/api/v1/records/record/${rec.dbId}/archive`, { method: "PUT" });
      if (!response.ok) throw new Error("Fehler beim Archivieren");
      toast.success("Aufnahme archiviert");
      if (selectedRecording?.id === id) setSelectedRecording(null);
      fetchRecords();
    } catch (error) {
      console.error(error);
      toast.error("Fehler beim Archivieren");
    }
  };

  const handleUnarchive = async (id: string) => {
    const rec = recordings.find(r => r.id === id);
    if (!rec?.dbId) return;
    try {
      const response = await fetch(`/api/v1/records/record/${rec.dbId}/unarchive`, { method: "PUT" });
      if (!response.ok) throw new Error("Fehler beim Wiederherstellen");
      toast.success("Aufnahme wiederhergestellt");
      if (selectedRecording?.id === id) setSelectedRecording(null);
      fetchRecords();
    } catch (error) {
      console.error(error);
      toast.error("Fehler beim Wiederherstellen");
    }
  };

  const handleRecordingStart = (recordingData: any) => {
    setActiveSessionId(recordingData.session_id);
    setUnfinishedSessionId(recordingData.session_id);
    const cat = categories.find(c => c.id.toString() === categoryId);
    const tempRecording: Recording = {
      id: recordingData.session_id,
      dbId: recordingData.id,
      title: newTitle || recordingData.title || `Aufnahme ${recordings.length + 1}`,
      categoryId: categoryId ? parseInt(categoryId) : null,
      categoryName: cat?.name || newCategoryName || "Unkategorisiert",
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
      const res = await fetch(`/api/v1/records/by-session/${sessionId}`);
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
        categoryName: categories.find(c => c.id === data.category_id)?.name || "Unkategorisiert",
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
      toast.error("Fehler beim Abrufen der Aufnahme");
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
      const result = await fetch(`/api/v1/records/record/${recording.dbId}`);
      if (!result.ok) throw new Error("Failed to fetch record");
      const data = await result.json();
      setSelectedRecording({
        id: data.session_id,
        dbId: data.id,
        title: data.title,
        categoryId: data.category_id,
        categoryName: categories.find(c => c.id === data.category_id)?.name || "Unkategorisiert",
        timestamp: data.timestamp,
        content: data.content || "",
        summarize: data.summarize || "",
        userid: data.user_id.toString(),
        taskId: data.task_id || recording.taskId,
      });
    } catch (err) {
      console.error(err);
      toast.error("Fehler beim Laden der Aufnahme");
    }
  };

  const handleSaveRecording = async (id: string, content: string, summarize: string) => {
    const rec = recordings.find(r => r.id === id);
    if (!rec?.dbId) return;
    try {
      const res = await fetch(`/api/v1/records/record/${rec.dbId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, summarize }),
      });
      if (!res.ok) throw new Error("Failed to save");
      toast.success("Aufnahme gespeichert");
      setRecordings(prev => prev.map(r => r.id === id ? { ...r, content, summarize } : r));
      if (selectedRecording?.id === id) {
        setSelectedRecording(prev => prev ? { ...prev, content, summarize } : null);
      }
    } catch (err) {
      console.error(err);
      toast.error("Fehler beim Speichern");
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
        await fetch(`/api/v1/records/cancel-session/${userId}`, { method: "DELETE" });
      } catch (err) {
        console.error(err);
      }
      setUnfinishedSessionId(null);
    }
    if (!newTitle.trim()) setNewTitle(`Aufnahme ${recordings.length + 1}`);
    if (!newCategoryName.trim()) setNewCategoryName("Unkategorisiert");
    setIsDialogOpen(false);
    setTimeout(() => {
      if (showArchived) setShowArchived(false);
      else fetchRecords();
      setActiveSessionId("new");
    }, 300);
  };

  return (
    <div className="relative min-h-screen bg-background flex">
      <Sidebar
        recordings={recordings}
        onSelectRecording={handleSelectRecording}
        selectedId={selectedRecording?.id}
        activeSessionId={unfinishedSessionId || undefined}
        onDeleteRecording={handleDelete}
        onArchiveRecording={handleArchive}
        onUnarchiveRecording={handleUnarchive}
        showArchived={showArchived}
        onToggleArchived={setShowArchived}
        mobileOpen={mobileSidebarOpen}
        onMobileOpenChange={setMobileSidebarOpen}
      />
      <main className="flex-1 min-w-0 overflow-auto bg-muted/30 flex flex-col">
        <div className="md:hidden flex items-center gap-2 px-3 py-2 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex-shrink-0">
          <Button variant="ghost" size="icon" onClick={() => setMobileSidebarOpen(true)}>
            <Menu className="w-5 h-5" />
            <span className="sr-only">Menü öffnen</span>
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
                  const ok = confirm("Aufnahme wirklich abbrechen? Diese kann nicht wiederhergestellt werden.");
                  if (!ok) return;
                  // Wait for pending chunk uploads before cancelling on the server,
                  // so in-flight uploads don't create orphaned files after cleanup.
                  try { await recorderRef.current?.waitForUploads(); } catch {}
                  setActiveSessionId(null);
                  setUnfinishedSessionId(null);
                  setSelectedRecording(null);
                  try {
                    await fetch(`/api/v1/records/cancel-session/${userId}`, { method: "DELETE" });
                  } catch (err) {
                    console.error(err);
                    toast.error("Fehler beim Abbrechen der Aufnahme");
                  }
                  fetchRecords();
                }}
              >
                Abbrechen
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
                Zur Übersicht
              </Button>
            </div>
          </div>
        ) : !selectedRecording ? (
          <div className="flex flex-col items-center justify-center h-full space-y-4 text-center">
            {unfinishedSessionId && (
              <div className="w-full max-w-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-4 flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/40 flex items-center justify-center flex-shrink-0">
                  <Radio className="w-5 h-5 text-red-500 animate-pulse" />
                </div>
                <div className="flex-1 text-left">
                  <p className="text-sm font-semibold text-red-700 dark:text-red-400">Unfertige Aufnahme</p>
                  <p className="text-xs text-red-600/70 dark:text-red-400/70">Eine Aufnahme wurde unterbrochen und kann fortgesetzt werden.</p>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <Button
                    size="sm"
                    onClick={() => setActiveSessionId(unfinishedSessionId)}
                  >
                    Fortsetzen
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-red-600 hover:text-red-700 hover:bg-red-100 dark:hover:bg-red-900/30"
                    onClick={async () => {
                      const ok = confirm("Aufnahme wirklich verwerfen?");
                      if (!ok) return;
                      try {
                        await fetch(`/api/v1/records/cancel-session/${userId}`, { method: "DELETE" });
                      } catch (err) {
                        console.error(err);
                      }
                      setUnfinishedSessionId(null);
                      fetchRecords();
                    }}
                  >
                    Verwerfen
                  </Button>
                </div>
              </div>
            )}

            <div className="space-y-2">
              <h1 className="text-3xl font-bold">Willkommen bei openDox</h1>
              <p className="text-muted-foreground">Wählen Sie eine Aufnahme aus oder starten Sie eine neue, um loszulegen.</p>
            </div>

            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button size="lg">Neue Aufnahme starten</Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                  <DialogTitle>Neue Aufnahme</DialogTitle>
                  <DialogDescription>
                    Geben Sie der Aufnahme einen Namen und eine Kategorie, um sie später leichter zu finden.
                  </DialogDescription>
                </DialogHeader>

                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <label htmlFor="title" className="text-sm font-medium">Titel</label>
                    <Input
                      id="title"
                      value={newTitle}
                      onChange={(e) => setNewTitle(e.target.value)}
                      placeholder="z.B. Patienten-Anamnese"
                      autoFocus
                    />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm font-medium">Kategorie</label>
                    <Select value={categoryId || ""} onValueChange={(val) => {
                      setCategoryId(val);
                      const cat = categories.find(c => c.id.toString() === val);
                      setNewCategoryName(cat?.name || "");
                    }}>
                      <SelectTrigger>
                        <SelectValue placeholder="Kategorie auswählen..." />
                      </SelectTrigger>
                      <SelectContent>
                        {categories.map((cat) => (
                          <SelectItem key={cat.id} value={cat.id.toString()}>{cat.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <Alert variant="destructive" className="mt-2">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertTitle>Wichtiger Hinweis</AlertTitle>
                    <AlertDescription className="text-sm leading-relaxed">
                      Dieses Tool ist kein Medizinprodukt gemäß Medizinproduktegesetz (MPG). Es dient ausschließlich der Unterstützung bei der Dokumentation.
                      Alle maschinell erstellten Transkriptionen und Zusammenfassungen müssen von qualifiziertem Fachpersonal überprüft werden.
                      Es ersetzt keine ärztliche Diagnose, Beratung oder Therapieempfehlung.
                    </AlertDescription>
                  </Alert>
                </div>

                <DialogFooter>
                  <DialogClose asChild>
                    <Button type="button" variant="secondary">Abbrechen</Button>
                  </DialogClose>
                  <Button onClick={handleStartRecordingSession}>Aufnahme starten</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        ) : (
          <TranscriptView
            transcript={selectedRecording}
            onNewRecording={async () => {
              setSelectedRecording(null);
              setCategoryId(null);
              setNewTitle("");
              setNewCategoryName("");
              await fetchRecords();
            }}
            onSave={handleSaveRecording}
          />
        )}
        </div>
      </main>
    </div>
  );
};

export default Dashboard;
