/*
  openDox - Medical transcription platform
  Copyright (C) 2025  crizz <christopher.abanilla@gmx.de>

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

import { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import Recorder from "@/components/Recorder";
import TranscriptView from "@/components/TranscriptView";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { AlertTriangle } from "lucide-react";
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
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [selectedRecording, setSelectedRecording] = useState<Recording | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newCategoryName, setNewCategoryName] = useState("");
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);

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

    const savedSession = localStorage.getItem("currentSession");
    if (savedSession) {
      const rec = JSON.parse(savedSession);
      if (rec.user_id?.toString() === userId) {
        setActiveSessionId(rec.session_id);
      } else {
        localStorage.removeItem("currentSession");
      }
    }
  }, [userId, showArchived]);

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
    setSelectedRecording(tempRecording);
  };

  const handleFinalTranscription = async (sessionId: string, taskId?: string | number) => {
    setActiveSessionId(null);
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
    try {
      if (!recording.dbId) {
        setSelectedRecording(recording);
        setActiveSessionId(null);
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
      setActiveSessionId(null);
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

  const handleStartRecordingSession = () => {
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
        onDeleteRecording={handleDelete}
        onArchiveRecording={handleArchive}
        onUnarchiveRecording={handleUnarchive}
        showArchived={showArchived}
        onToggleArchived={setShowArchived}
      />
      <main className="flex-1 overflow-auto bg-muted/30">
        {activeSessionId ? (
          <div className="flex flex-col items-center justify-center h-full">
            <Recorder
              userId={userId}
              title={newTitle}
              categoryId={categoryId}
              onRecordingStart={handleRecordingStart}
              onFinalTranscription={handleFinalTranscription}
              autoStart={true}
            />
            <Button variant="ghost" className="mt-4" onClick={() => setActiveSessionId(null)}>Abbrechen</Button>
          </div>
        ) : !selectedRecording ? (
          <div className="flex flex-col items-center justify-center h-full space-y-4 text-center">
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
      </main>
    </div>
  );
};

export default Dashboard;
