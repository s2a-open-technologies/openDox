import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Mic, StopCircle } from "lucide-react";

interface NewRecordViewProps {
  onStartRecording: () => void;
  onStopRecording: () => void;
  isRecording: boolean;
  transcript: string;
}

export default function NewRecordView({
  onStartRecording,
  onStopRecording,
  isRecording,
  transcript,
}: NewRecordViewProps) {
  return (
    <div className="h-full p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-foreground">Neue Aufnahme</h2>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Aufnahmetext</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="prose prose-slate dark:prose-invert max-w-none min-h-[200px] border rounded-lg p-4 bg-background">
            {transcript ? (
              <p className="whitespace-pre-wrap">{transcript}</p>
            ) : (
              <p className="text-muted-foreground">Hier erscheint Ihr Transkript.</p>
            )}
          </div>

          <div className="flex flex-col items-center gap-2 pt-4">
            <Button
              onClick={isRecording ? onStopRecording : onStartRecording}
              disabled={false}
              className="w-20 h-20 rounded-full bg-red-500 hover:bg-red-600"
            >
              {isRecording ? (
                <StopCircle className="h-10 w-10 text-white" />
              ) : (
                <Mic className="h-10 w-10 text-white" />
              )}
            </Button>
            <p className="text-sm text-muted-foreground">
              {isRecording ? "Aufnahme läuft... Klicken Sie zum Beenden." : "Klicken Sie auf das Mikrofon, um zu starten."}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
