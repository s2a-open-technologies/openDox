import { useState, useEffect } from "react";
import TopBar from "@/components/TopBar";
import Sidebar from "@/components/Sidebar";
import Recorder from "@/components/Recorder";
import TranscriptView from "@/components/TranscriptView";

export interface Recording {
  id: string;
  title: string;
  category: string;
  date: string;
  transcript: string;
  userid: string;
}

const Dashboard = () => {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [selectedRecording, setSelectedRecording] = useState<Recording | null>(null);
  const [currentTranscript, setCurrentTranscript] = useState<string>("");
  const [isRecording, setIsRecording] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("recordings");
    if (stored) {
      setRecordings(JSON.parse(stored));
    }
  }, []);

  const handleNewRecording = (transcript: string) => {
    const newRecording: Recording = {
      id: Date.now().toString(),
      title: `Aufnahme ${recordings.length + 1}`,
      category: "Unkategorisiert",
      date: new Date().toLocaleString("de-DE"),
      transcript,
      userid: "1",
    };
    const updated = [newRecording, ...recordings];
    setRecordings(updated);
    localStorage.setItem("recordings", JSON.stringify(updated));
    setCurrentTranscript(transcript);
    setSelectedRecording(null);
    setIsRecording(false); // Aufnahme beenden
  };

  const handleSelectRecording = (recording: Recording) => {
    setSelectedRecording(recording);
    setCurrentTranscript("");
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
          {!selectedRecording && !currentTranscript ? (
            <Recorder
              onTranscriptReceived={handleNewRecording}
            />
          ) : (
            <TranscriptView
              transcript={selectedRecording?.transcript || currentTranscript}
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
