import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface AudioSettings {
  audio_download_enabled: boolean;
  audio_bitrate: string;
  audio_sample_rate: number;
  audio_format: string;
}

const BITRATE_FORMATS = new Set(["mp3", "ogg"]);

export function AudioConfig({ readOnly = false }: { readOnly?: boolean }) {
  const { authFetch } = useAuth();
  const [config, setConfig] = useState<AudioSettings>({
    audio_download_enabled: true,
    audio_bitrate: "64k",
    audio_sample_rate: 16000,
    audio_format: "mp3",
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    authFetch('/api/v1/settings/audio-settings/')
      .then(res => res.json())
      .then((data: any) => {
        setConfig({
          audio_download_enabled: data.audio_download_enabled ?? true,
          audio_bitrate: data.audio_bitrate ?? "64k",
          audio_sample_rate: data.audio_sample_rate ?? 16000,
          audio_format: data.audio_format ?? "mp3",
        });
      })
      .catch(console.error);
  }, []);

  const updateField = (field: keyof AudioSettings, value: boolean | string | number) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };

  const saveConfig = async () => {
    setLoading(true);
    try {
      const res = await authFetch('/api/v1/settings/audio-settings/', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (res.ok) {
        toast.success('Audio-Einstellungen gespeichert');
      } else {
        toast.error('Speichern fehlgeschlagen');
      }
    } catch {
      toast.error('Verbindungsfehler');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Audio-Download</CardTitle>
        <CardDescription>
          Audio-Export für Aufnahmen (mono, konfigurierbares Format/Qualität). Gilt nur für neue Aufnahmen.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center gap-3">
          <Switch
            checked={config.audio_download_enabled}
            disabled={readOnly}
            onCheckedChange={(checked) => updateField('audio_download_enabled', checked)}
          />
          <Label htmlFor="audio-enabled">Audio speichern</Label>
        </div>
        <div className="space-y-2">
          <Label htmlFor="audio-format">Dateiformat</Label>
          <select
            id="audio-format"
            value={config.audio_format}
            disabled={readOnly}
            onChange={(e) => updateField('audio_format', e.target.value)}
            className="w-full px-3 py-2 border rounded-md bg-background"
          >
            <option value="mp3">MP3 (verlustbehaftet, kleinste Datei)</option>
            <option value="ogg">OGG/Opus (verlustbehaftet, modern & effizient)</option>
            <option value="flac">FLAC (verlustfrei komprimiert)</option>
            <option value="wav">WAV (unkomprimiert, größte Datei)</option>
          </select>
        </div>
        {BITRATE_FORMATS.has(config.audio_format) && (
          <div className="space-y-2">
            <Label htmlFor="audio-bitrate">Bitrate (Qualität/Größe)</Label>
            <select
              id="audio-bitrate"
              value={config.audio_bitrate}
              disabled={readOnly}
              onChange={(e) => updateField('audio_bitrate', e.target.value)}
              className="w-full px-3 py-2 border rounded-md bg-background"
            >
              <option value="32k">32 kbit/s (~0,4 MB/min)</option>
              <option value="48k">48 kbit/s (~0,6 MB/min)</option>
              <option value="64k">64 kbit/s (~0,8 MB/min)</option>
              <option value="96k">96 kbit/s (~1,2 MB/min)</option>
              <option value="128k">128 kbit/s (~1,5 MB/min)</option>
              <option value="160k">160 kbit/s (~1,9 MB/min)</option>
              <option value="192k">192 kbit/s (~2,3 MB/min)</option>
              <option value="256k">256 kbit/s (~3,0 MB/min)</option>
              <option value="320k">320 kbit/s (~3,8 MB/min)</option>
            </select>
          </div>
        )}
        <div className="space-y-2">
          <Label htmlFor="audio-sample-rate">Sample-Rate (Hz)</Label>
          <select
            id="audio-sample-rate"
            value={config.audio_sample_rate.toString()}
            disabled={readOnly}
            onChange={(e) => updateField('audio_sample_rate', parseInt(e.target.value))}
            className="w-full px-3 py-2 border rounded-md bg-background"
          >
            <option value="16000">16000 Hz (native, kleinste Datei)</option>
            <option value="22050">22050 Hz</option>
            <option value="44100">44100 Hz (Standard-Audio, größer)</option>
          </select>
        </div>
        <p className="text-xs text-muted-foreground">
          Mono erzwungen. Wenn ffmpeg nicht verfügbar ist, wird kein Audio gespeichert.
        </p>
        <div className="pt-4 flex justify-end">
          <Button onClick={saveConfig} disabled={loading || readOnly}>
            {loading ? 'Speichern...' : 'Speichern'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}