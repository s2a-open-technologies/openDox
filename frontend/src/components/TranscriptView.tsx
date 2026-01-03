import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Mic } from "lucide-react";
import { TfiReload } from "react-icons/tfi";

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
      <div className="flex gap-4">
        <Card className="w-3/5">
          <CardHeader>
            <CardTitle className="text-lg">{transcript?.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="prose prose-slate dark:prose-invert max-w-none">
              <p className="text-foreground whitespace-pre-wrap">{transcript?.content}</p>
            </div>
          </CardContent>
        </Card>
        <Card className="w-2/5">
          <CardHeader>
            <div className="flex items-end justify-between">
            <CardTitle className="text-lg">Zusammenfassung</CardTitle>
            
              <Button><TfiReload /></Button>
            </div>

          </CardHeader>
          <CardContent>

            <div className="prose prose-slate dark:prose-invert max-w-none">
              <p className="text-foreground whitespace-pre-wrap">{transcript?.summarize}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default TranscriptView;
