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

          {/* Aufnahmebutton*/}
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
