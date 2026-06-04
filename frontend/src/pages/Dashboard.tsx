import { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import Recorder from "@/components/Recorder";
import TranscriptView from "@/components/TranscriptView";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

import {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogClose,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"

export interface Recording {
  id: string;
  title: string;
  category: string;
  timestamp: string;
  transcript: string;
  summary?: string;
  userid: string;
  taskId?: string | number;
}

const Dashboard = () => {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [selectedRecording, setSelectedRecording] = useState<Recording | null>(null);
  const [currentTranscript, setCurrentTranscript] = useState<string>("");
  const [isRecording, setIsRecording] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newCategory, setNewCategory] = useState("");
  const [showRecorder, setShowRecorder] = useState(false);
  const [userId, setUserId] = useState("1"); // Beispielbenutzer-ID
  const [showArchived, setShowArchived] = useState(false);

  const fetchRecords = async () => {
    try {
      const response = await fetch(`/api/v1/records/list-records/${userId}?archived=${showArchived}`);
      if (response.ok) {
        const data = await response.json();
        setRecordings(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchRecords();

    // Check for active session in localStorage to restore state
    const savedSession = localStorage.getItem("currentSession");
    if (savedSession) {
      setShowRecorder(true);
    }
  }, [userId, showArchived]);

  const handleDelete = async (id: string) => {
    try {
      if (!confirm("Möchten Sie diese Aufnahme wirklich unwiderruflich löschen?")) return;

      const response = await fetch(`/api/v1/records/record/${id}`, {
        method: "DELETE",
      });

      if (!response.ok) throw new Error("Fehler beim Löschen");

      toast.success("Aufnahme gelöscht");
      if (selectedRecording?.id === id) {
        setSelectedRecording(null);
      }
      fetchRecords();
    } catch (error) {
      console.error(error);
      toast.error("Fehler beim Löschen der Aufnahme");
    }
  };

  const handleArchive = async (id: string) => {
    try {
      const response = await fetch(`/api/v1/records/record/${id}/archive`, {
        method: "PUT",
      });

      if (!response.ok) throw new Error("Fehler beim Archivieren");

      toast.success("Aufnahme archiviert");
      if (selectedRecording?.id === id) {
        setSelectedRecording(null);
      }
      fetchRecords();
    } catch (error) {
      console.error(error);
      toast.error("Fehler beim Archivieren");
    }
  };

  const handleUnarchive = async (id: string) => {
    try {
      const response = await fetch(`/api/v1/records/record/${id}/unarchive`, {
        method: "PUT",
      });

      if (!response.ok) throw new Error("Fehler beim Wiederherstellen");

      toast.success("Aufnahme wiederhergestellt");
      if (selectedRecording?.id === id) {
        setSelectedRecording(null);
      }
      fetchRecords();
    } catch (error) {
      console.error(error);
      toast.error("Fehler beim Wiederherstellen");
    }
  };

  const handleNewRecording = async (transcript: string, taskId?: string | number) => {
    try {
      // Zuerst die Aufnahme im Backend speichern
      const response = await fetch('/api/v1/records/record/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          title: newTitle || `Aufnahme ${recordings.length + 1}`,
          category: newCategory || "Unkategorisiert",
          transcript: transcript,
          timestamp: new Date().toISOString(),
        }),
      });

      if (!response.ok) {
        throw new Error('Fehler beim Speichern der Aufnahme');
      }

      const newRecordingData = await response.json();

      // Neue Aufnahme lokal hinzufügen (ersetze temporären Eintrag falls vorhanden)
      const finalRecording: Recording = {
        id: newRecordingData.id || newRecordingData.session_id,
        title: newRecordingData.title,
        category: newRecordingData.category,
        timestamp: new Date(newRecordingData.created_at).toLocaleString("de-DE"),
        transcript,
        userid: userId,
        taskId: taskId, // Store task ID
      };

      // Wenn wir gerade archivierte Aufnahmen anzeigen, wechseln wir zurück zu den aktuellen
      if (showArchived) {
        setShowArchived(false);
        // fetchRecords wird durch den useEffect getriggert, aber wir setzen den State manuell optimistisch
        setRecordings(prev => [finalRecording, ...prev]);
      } else {
        setRecordings(prev => {
          const exists = prev.find(r => r.id === finalRecording.id || r.id === newRecordingData.session_id);
          if (exists) {
            return prev.map(r => (r.id === finalRecording.id || r.id === newRecordingData.session_id) ? finalRecording : r);
          }
          return [finalRecording, ...prev];
        });
      }

      // Aktualisiere die lokale Auswahl & wechsle zur TranscriptView
      setSelectedRecording(finalRecording);
      setCurrentTranscript(""); // Ensure TranscriptView uses selectedRecording

      // Zurücksetzen der Zustände
      setIsRecording(false);
      setIsDialogOpen(false);
      setShowRecorder(false); // Switch to TranscriptView
      setNewTitle("");
      setNewCategory("");

      toast.success("Aufnahme erfolgreich gespeichert");
    } catch (error) {
      console.error("Fehler beim Speichern der Aufnahme:", error);
      toast.error("Fehler beim Speichern der Aufnahme");
    }
  };

  const handleSelectRecording = async (recording: Recording) => {
    const result = await fetch(`/api/v1/records/record/${recording.id}`,{
      method: "GET"
    })
    
    const data = await result.json();
    console.log(data);
    setSelectedRecording(recording);
    setCurrentTranscript(data);
    setShowRecorder(false); // Hide recorder when selecting an existing recording
  };

  const handleRecordingStart = (recordingData: any) => {
    // Create a temporary recording entry for immediate sidebar feedback
    const tempRecording: Recording = {
      id: recordingData.session_id || Date.now().toString(),
      title: newTitle || recordingData.title || `Aufnahme ${recordings.length + 1}`,
      category: newCategory || "Unkategorisiert",
      timestamp: new Date().toLocaleString("de-DE"),
      transcript: "",
      userid: userId,
      taskId: undefined,
    };

    // If we're in archive view, switch back to main view
    if (showArchived) {
      setShowArchived(false);
    }

    // Add to list and select it immediately
    setRecordings(prev => [tempRecording, ...prev]);
    setSelectedRecording(tempRecording);
  };

  const handleStartRecordingSession = () => {
    if (!newTitle.trim()) {
      setNewTitle(`Aufnahme ${recordings.length + 1}`);
    }
    if (!newCategory.trim()) {
      setNewCategory("Unkategorisiert");
    }
    setIsDialogOpen(false);
    setTimeout(async () => {
      // Aktualisiere die Liste der Aufnahmen vor dem Starten der neuen Aufnahme
      if (showArchived) setShowArchived(false);
      else await fetchRecords();

      setShowRecorder(true);
    }, 300); // Small delay to allow dialog to close smoothly
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
        {showRecorder ? (
          <div className="flex flex-col items-center justify-center h-full">
            <Recorder
              userId="1"
              title={newTitle}
              onRecordingStart={handleRecordingStart}
              onFinalTranscription={handleNewRecording}
              autoStart={true}
            />
            <Button variant="ghost" className="mt-4" onClick={() => setShowRecorder(false)}>Abbrechen</Button>
          </div>
        ) : !selectedRecording && !currentTranscript ? (
          <div className="flex flex-col items-center justify-center h-full space-y-4 text-center">
            <div className="space-y-2">
              <h1 className="text-3xl font-bold">Willkommen bei openDox</h1>
              <p className="text-muted-foreground">Wählen Sie eine Aufnahme aus oder starten Sie eine neue, um loszulegen.</p>
            </div>

            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button size="lg">Neue Aufnahme starten</Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
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
                    <label htmlFor="category" className="text-sm font-medium">Kategorie</label>
                    <Input
                      id="category"
                      value={newCategory}
                      onChange={(e) => setNewCategory(e.target.value)}
                      placeholder="z.B. Kardiologie"
                    />
                  </div>
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
              setCurrentTranscript("");
              setShowRecorder(false); // This returns to the "Start Screen" (Welcome to openDox)
              // Optionally fetch records if needed to keep list fresh, though strictly not necessary for the view
              await fetchRecords();
            }}
          />
        )}
      </main>
    </div>
  );
};

export default Dashboard;
