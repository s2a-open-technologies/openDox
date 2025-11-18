import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Mic } from "lucide-react";

interface TranscriptViewProps {
  transcript: string;
  onNewRecording: () => void;
}

const TranscriptView = ({ transcript, onNewRecording }: TranscriptViewProps) => {
  return (
    <div className="h-full p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-foreground">Transkript</h2>
        <Button onClick={onNewRecording} variant="outline" size="sm">
          <Mic className="w-4 h-4 mr-2" />
          Neue Aufnahme
        </Button>
      </div>
      
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Aufnahmetext</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="prose prose-slate dark:prose-invert max-w-none">
            <p className="text-foreground whitespace-pre-wrap">{transcript}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default TranscriptView;
