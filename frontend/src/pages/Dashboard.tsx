import { useState, useEffect } from "react";
import TopBar from "@/components/TopBar";
import Sidebar from "@/components/Sidebar";
import Recorder from "@/components/Recorder";
import TranscriptView from "@/components/TranscriptView";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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
  DialogLabel, 
} from "@/components/ui/dialog"

export interface Recording {
  id: string;
  title: string;
  category: string;
  timestamp: string;
  transcript: string;
  userid: string;
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

  useEffect(() => {
    const fetchRecords = async () => {
      try {
        const response = await fetch(`/api/v1/records/record/list-records/${userId}`);
        if (response.ok) {
          const data = await response.json();
          setRecordings(data);
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchRecords();
  }, [userId]);

  const handleNewRecording = (transcript: string) => {
    const newRecording: Recording = {
      id: Date.now().toString(),
      title: newTitle || `Aufnahme ${recordings.length + 1}`,
      category: newCategory || "Unkategorisiert",
      date: new Date().toLocaleString("de-DE"),
      transcript,
      userid: userId,
    };
    const updated = [newRecording, ...recordings];
    setRecordings(updated);
    localStorage.setItem("recordings", JSON.stringify(updated));
    setCurrentTranscript(transcript);
    setSelectedRecording(null);
    setIsRecording(false);
    setIsDialogOpen(false);
    setShowRecorder(false);
    setNewTitle("");
    setNewCategory("");
  };

  const handleSelectRecording = (recording: Recording) => {
    setSelectedRecording(recording);
    setCurrentTranscript("");
  };

  const handleStartRecordingSession = () => {
    setIsDialogOpen(false);
    setShowRecorder(true);
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          recordings={recordings}
          onSelectRecording={handleSelectRecording}
          selectedId={selectedRecording?.id}
        />
        <main className="flex-1 overflow-auto">
          {showRecorder ? (
            <div className="flex flex-col items-center justify-center h-full">
              <Recorder
                userId="1"
                title={newTitle}
                onFinalTranscription={handleNewRecording}
                autoStart={true}
              />
              <Button variant="ghost" className="mt-4" onClick={() => setShowRecorder(false)}>Abbrechen</Button>
            </div>
          ) : !selectedRecording && !currentTranscript ? (
            <div className="flex flex-col items-center justify-center h-full space-y-4">
              <div className="text-center space-y-2">
                <h2 className="text-2xl font-semibold">Willkommen im Dashboard</h2>
                <p className="text-muted-foreground">Wählen Sie eine Aufnahme aus oder starten Sie eine neue.</p>
              </div>
              
              <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogTrigger asChild>
                  <Button size="lg">Neue Aufnahme starten</Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-[500px]">
                  <DialogHeader>
                    <DialogTitle>Neue Aufnahme</DialogTitle>
                    <DialogDescription>
                      Geben Sie der Aufnahme einen Namen und eine Kategorie.
                    </DialogDescription>
                  </DialogHeader>
                  
                  <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                      <label htmlFor="title" className="text-sm font-medium">Titel</label>
                      <Input
                        id="title"
                        value={newTitle}
                        onChange={(e) => setNewTitle(e.target.value)}
                        placeholder="z.B. Meeting Protokoll"
                      />
                    </div>
                    <div className="grid gap-2">
                      <label htmlFor="category" className="text-sm font-medium">Kategorie</label>
                      <Input
                        id="category"
                        value={newCategory}
                        onChange={(e) => setNewCategory(e.target.value)}
                        placeholder="z.B. Arbeit, Privat"
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button onClick={handleStartRecordingSession}>Weiter</Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          ) : (
            <TranscriptView
              transcript={selectedRecording}
              onNewRecording={() => {
                setSelectedRecording(null);
                setCurrentTranscript("");
              }}
            />
          )}
        </main>
      </div>
    </div>
  );
};

export default Dashboard;
