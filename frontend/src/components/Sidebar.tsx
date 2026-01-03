import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { FileAudio } from "lucide-react";
import type { Recording } from "@/pages/Dashboard";

interface SidebarProps {
  recordings: Recording[];
  onSelectRecording: (recording: Recording) => void;
  selectedId?: string;
}

const Sidebar = ({ recordings, onSelectRecording, selectedId }: SidebarProps) => {
  return (
    <aside className="w-64 border-r border-border bg-card flex flex-col">
      <div className="p-4 border-b border-border">
        <h2 className="font-semibold text-foreground">Aufnahmen</h2>
        <p className="text-xs text-muted-foreground mt-1">{recordings.length} gesamt</p>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {recordings.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground text-sm">
              Noch keine Aufnahmen vorhanden
            </div>
          ) : (
            recordings.map((recording) => (
              <button
                key={recording.id}
                onClick={() => onSelectRecording(recording)}
                className={cn(
                  "w-full p-3 rounded-lg text-left hover:bg-accent transition-colors",
                  selectedId === recording.id && "bg-accent"
                )}
              >
                <div className="flex items-start gap-3">
                  <FileAudio className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {recording.title}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {recording.timestamp}
                    </p>
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </ScrollArea>
    </aside>
  );
};

export default Sidebar;
