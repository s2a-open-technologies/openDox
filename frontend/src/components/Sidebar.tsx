import { ScrollArea } from "@/components/ui/scroll-area";
import { Logo } from "@/components/Logo";
import { cn } from "@/lib/utils";
import { FileAudio, MoreHorizontal, Archive, Trash2, RotateCcw, Library } from "lucide-react";
import UserDropdown from "@/components/UserDropdown";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import type { Recording } from "@/pages/Dashboard";

interface SidebarProps {
  recordings: Recording[];
  onSelectRecording: (recording: Recording) => void;
  selectedId?: string;
  onDeleteRecording?: (id: string) => void;
  onArchiveRecording?: (id: string) => void;
  onUnarchiveRecording?: (id: string) => void;
  showArchived?: boolean;
  onToggleArchived?: (show: boolean) => void;
}

const Sidebar = ({
  recordings,
  onSelectRecording,
  selectedId,
  onDeleteRecording,
  onArchiveRecording,
  onUnarchiveRecording,
  showArchived = false,
  onToggleArchived,
}: SidebarProps) => {
  return (
    <aside className={cn("w-80 bg-background flex flex-col border-r border-border h-screen")}>
      <div className="p-4 border-b border-border z-10 relative bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex flex-col gap-2">
        <div className="flex items-center justify-start w-full">
          <Logo className="h-20 w-auto" />
        </div>
      </div>

      <div className="px-2 pt-2 flex gap-2">
        <Button
          variant={!showArchived ? "secondary" : "ghost"}
          className={cn("flex-1", !showArchived && "bg-zinc-100 dark:bg-zinc-800 font-medium")}
          onClick={() => onToggleArchived?.(false)}
          title="Aktuell"
        >
          <Library className="w-4 h-4" />
        </Button>
        <Button
          variant={showArchived ? "secondary" : "ghost"}
          className={cn("flex-1", showArchived && "bg-zinc-100 dark:bg-zinc-800 font-medium")}
          onClick={() => onToggleArchived?.(true)}
          title="Archiv"
        >
          <Archive className="w-4 h-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1 py-3 px-2">
        <div className="space-y-1">
          {recordings.length === 0 ? (
            <div className="p-6 text-center text-muted-foreground">
              <FileAudio className="w-8 h-8 mx-auto mb-2" />
              <p className="text-sm">
                {showArchived ? "Keine archivierten Aufnahmen" : "Keine Aufnahmen"}
              </p>
            </div>
          ) : (
            recordings.map((recording) => (
              <div
                key={recording.id}
                className={cn(
                  "group relative w-full rounded-lg transition-all duration-200",
                  selectedId === recording.id
                    ? "bg-blue-50 dark:bg-zinc-800/80 ring-1 ring-primary/20"
                    : "hover:bg-zinc-100 dark:hover:bg-zinc-800"
                )}
              >
                <button
                  onClick={() => onSelectRecording(recording)}
                  className="w-full text-left px-4 py-3 pr-10"
                >
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "w-8 h-8 rounded-full flex items-center justify-center transition-colors",
                      selectedId === recording.id
                        ? "bg-primary/10 text-primary"
                        : "bg-zinc-100 dark:bg-zinc-800 text-muted-foreground"
                    )}>
                      <FileAudio className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={cn(
                        "text-sm font-semibold truncate transition-colors",
                        selectedId === recording.id ? "text-primary" : "text-foreground"
                      )}>
                        {recording.title}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {recording.timestamp}
                      </p>
                    </div>
                  </div>
                </button>

                <div className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-zinc-200 dark:hover:bg-zinc-700">
                        <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {showArchived ? (
                        <DropdownMenuItem onClick={() => onUnarchiveRecording?.(recording.id)}>
                          <RotateCcw className="w-4 h-4 mr-2" />
                          Wiederherstellen
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem onClick={() => onArchiveRecording?.(recording.id)}>
                          <Archive className="w-4 h-4 mr-2" />
                          Archivieren
                        </DropdownMenuItem>
                      )}

                      <DropdownMenuSeparator />

                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={() => onDeleteRecording?.(recording.id)}
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        Löschen
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            ))
          )}
        </div>
      </ScrollArea>
      <div className="p-2 border-t border-border">
        <UserDropdown />
      </div>
    </aside >
  );
};

export default Sidebar;
