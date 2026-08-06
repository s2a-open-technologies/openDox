/*
  openDox - Medical transcription platform
  Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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

import { useState, useEffect, useCallback } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Tabs,
    TabsContent,
    TabsList,
    TabsTrigger,
} from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from '@/contexts/AuthContext';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

interface WhisperSettings {
    live_backend: string;
    live_api_endpoint: string;
    live_api_key: string;
    live_api_model: string;
    final_backend: string;
    final_api_endpoint: string;
    final_api_key: string;
    final_api_model: string;
    language: string;
    chunk_length_s: number;
    overlap_s: number;
    left_context_s: number;
    // Anti-hallucination / faster-whisper tuning
    temperature: number;
    vad_filter: boolean;
    vad_min_silence_ms: number;
    condition_on_previous_text: boolean;
    no_speech_threshold: number;
    compression_ratio_threshold: number;
    log_prob_threshold: number;
    hallucination_silence_threshold: number | null;
    live_beam_size: number;
    final_beam_size: number;
}

type TestResult = { ok: boolean; message: string } | null;

const WhisperConfig = ({ readOnly = false }: { readOnly?: boolean }) => {
    const { authFetch } = useAuth();
    const [liveTest, setLiveTest] = useState<{ status: 'idle' | 'testing' | 'done'; result: TestResult }>({
        status: 'idle',
        result: null,
    });
    const [finalTest, setFinalTest] = useState<{ status: 'idle' | 'testing' | 'done'; result: TestResult }>({
        status: 'idle',
        result: null,
    });
    const [config, setConfig] = useState<WhisperSettings>({
        live_backend: 'api',
        live_api_endpoint: '',
        live_api_key: '',
        live_api_model: '',
        final_backend: 'api',
        final_api_endpoint: '',
        final_api_key: '',
        final_api_model: '',
        language: 'de',
        chunk_length_s: 3,
        overlap_s: 0,
        left_context_s: 1,
        temperature: 0.0,
        vad_filter: true,
        vad_min_silence_ms: 500,
        condition_on_previous_text: false,
        no_speech_threshold: 0.6,
        compression_ratio_threshold: 2.4,
        log_prob_threshold: -1.0,
        hallucination_silence_threshold: null,
        live_beam_size: 1,
        final_beam_size: 5,
    });

    useEffect(() => {
        authFetch('/api/v1/settings/whisper-settings/')
            .then(res => res.json())
            .then((data: any) => {
                setConfig({
                    live_backend: data.live_backend || 'api',
                    live_api_endpoint: data.live_api_endpoint || '',
                    live_api_key: data.live_api_key || '',
                    live_api_model: data.live_api_model || '',
                    final_backend: data.final_backend || 'api',
                    final_api_endpoint: data.final_api_endpoint || '',
                    final_api_key: data.final_api_key || '',
                    final_api_model: data.final_api_model || '',
                    language: data.language || 'de',
                    chunk_length_s: data.chunk_length_s ?? 3,
                    overlap_s: data.overlap_s ?? 0,
                    left_context_s: data.left_context_s ?? 1,
                    temperature: data.temperature ?? 0.0,
                    vad_filter: data.vad_filter ?? true,
                    vad_min_silence_ms: data.vad_min_silence_ms ?? 500,
                    condition_on_previous_text: data.condition_on_previous_text ?? false,
                    no_speech_threshold: data.no_speech_threshold ?? 0.6,
                    compression_ratio_threshold: data.compression_ratio_threshold ?? 2.4,
                    log_prob_threshold: data.log_prob_threshold ?? -1.0,
                    hallucination_silence_threshold: data.hallucination_silence_threshold ?? null,
                    live_beam_size: data.live_beam_size ?? 1,
                    final_beam_size: data.final_beam_size ?? 5,
                });
            })
            .catch(console.error);
    }, []);

    const updateField = (key: keyof WhisperSettings, value: any) => {
        setConfig(prev => ({ ...prev, [key]: value }));
    };

    const saveConfig = async () => {
        try {
            const res = await authFetch('/api/v1/settings/whisper-settings/', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            if (res.ok) {
                toast.success('Einstellungen gespeichert');
            } else {
                toast.error('Speichern fehlgeschlagen');
            }
        } catch {
            toast.error('Verbindungsfehler');
        }
    };

    const testAsr = async (which: 'live' | 'final') => {
        const setter = which === 'live' ? setLiveTest : setFinalTest;
        setter({ status: 'testing', result: null });
        try {
            const res = await authFetch(`/api/v1/settings/asr-test/?backend=${which}`);
            const data = await res.json();
            if (data.ok) {
                const model = data.model ? ` · Modell: ${data.model}` : '';
                setter({ status: 'done', result: { ok: true, message: `Erreichbar${model}` } });
            } else {
                setter({ status: 'done', result: { ok: false, message: data.error || 'Nicht erreichbar' } });
            }
        } catch {
            setter({ status: 'done', result: { ok: false, message: 'Anfrage fehlgeschlagen' } });
        }
    };

    return (
        <div className="space-y-4">
            <h3 className="text-lg font-medium">Transkriptionsserver Konfiguration</h3>
            
            <Tabs defaultValue="general" className="w-full">
                <TabsList className={`grid w-full ${config.live_backend === 'api' ? 'grid-cols-2 sm:grid-cols-4' : 'grid-cols-3'}`}>
                    <TabsTrigger value="general">Allgemein</TabsTrigger>
                    <TabsTrigger value="live">Live</TabsTrigger>
                    <TabsTrigger value="final">Final</TabsTrigger>
                    {config.live_backend === 'api' && (
                        <TabsTrigger value="quality">Qualität</TabsTrigger>
                    )}
                </TabsList>

                <TabsContent value="general">
                    <Card>
                        <CardHeader>
                            <CardTitle>Allgemeine Einstellungen</CardTitle>
                            <CardDescription>Sprache</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label>Sprache</Label>
                                <Select value={config.language} disabled={readOnly} onValueChange={(v) => updateField('language', v)}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Wählen..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                    <SelectItem value="de">Deutsch</SelectItem>
                                    <SelectItem value="en">Englisch</SelectItem>
                                    <SelectItem value="fr">Französisch</SelectItem>
                                    <SelectItem value="es">Spanisch</SelectItem>
                                    <SelectItem value="it">Italienisch</SelectItem>
                                    <SelectItem value="auto">Automatisch (Spracherkennung)</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="live">
                    <Card>
                        <CardHeader>
                            <CardTitle>Live-Transkription</CardTitle>
                            <CardDescription>Echtzeit-Transkription während der Aufnahme</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="live-enabled">Live-Transkription aktiv</Label>
                                <Select value={config.live_backend} disabled={readOnly} onValueChange={(v) => updateField('live_backend', v)}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Wählen..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="parakeet">Parakeet (empfohlen)</SelectItem>
                                        <SelectItem value="api">Whisper API</SelectItem>
                                        <SelectItem value="disabled">Deaktiviert</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            
                            {config.live_backend !== 'disabled' && (
                                <>
                                    {config.live_backend === 'parakeet' && (
                                        <p className="text-sm text-muted-foreground">
                                            Parakeet läuft mit Silero-VAD-gesteuertem Streaming: Text
                                            wächst beim Sprechen und friert bei Sprechpausen ein.
                                            Chunk-Länge, Überlappung und Left-Context werden vom
                                            Server gesteuert und sind hier nicht relevant.
                                        </p>
                                    )}
                                    <div className="space-y-2">
                                        <Label>API Endpoint</Label>
                                        <Input
                                            placeholder={config.live_backend === 'parakeet' ? 'http://parakeet:5001/v1' : 'http://localhost:9000'}
                                            disabled={readOnly}
                                            value={config.live_api_endpoint}
                                            onChange={(e) => updateField('live_api_endpoint', e.target.value)}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>API Key (optional)</Label>
                                        <Input
                                            type="password"
                                            placeholder="Bearer Token"
                                            disabled={readOnly}
                                            value={config.live_api_key}
                                            onChange={(e) => updateField('live_api_key', e.target.value)}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Modell</Label>
                                        <Input
                                            placeholder="nemo-parakeet-tdt-0.6b-v3"
                                            disabled={readOnly}
                                            value={config.live_api_model}
                                            onChange={(e) => updateField('live_api_model', e.target.value)}
                                        />
                                    </div>
                                    {config.live_backend !== 'parakeet' && (
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <div className="space-y-2">
                                                <Label>Chunk-Länge (Sek.)</Label>
                                                <Input
                                                    type="number" min={1} max={10}
                                                    disabled={readOnly}
                                                    value={config.chunk_length_s}
                                                    onChange={(e) => updateField('chunk_length_s', parseInt(e.target.value) || 3)}
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Überlappung (Sek.)</Label>
                                                <Input
                                                    type="number" min={0} max={2} step={0.5}
                                                    disabled={readOnly}
                                                    value={config.overlap_s}
                                                    onChange={(e) => updateField('overlap_s', parseFloat(e.target.value) || 0)}
                                                />
                                            </div>
                                        </div>
                                    )}
                                </>
                            )}
                            <div className="flex gap-2 pt-2">
                                <Button
                                    variant="outline"
                                    onClick={() => testAsr('live')}
                                    disabled={config.live_backend === 'disabled' || liveTest.status === 'testing' || readOnly}
                                    className="gap-2"
                                >
                                    {liveTest.status === 'testing' && <Loader2 className="w-4 h-4 animate-spin" />}
                                    Verbindung testen
                                </Button>
                            </div>
                            {liveTest.result && (
                                <div className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${
                                    liveTest.result.ok
                                        ? 'border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-300'
                                        : 'border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300'
                                }`}>
                                    {liveTest.result.ok
                                        ? <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
                                        : <XCircle className="w-4 h-4 mt-0.5 shrink-0" />}
                                    <span>{liveTest.result.message}</span>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="final">
                    <Card>
                        <CardHeader>
                            <CardTitle>Finale Transkription</CardTitle>
                            <CardDescription>Qualitativ hochwertige Transkription nach der Aufnahme</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label>API Endpoint</Label>
                                <Input 
                                    placeholder="http://localhost:9000" 
                                    disabled={readOnly}
                                    value={config.final_api_endpoint} 
                                    onChange={(e) => updateField('final_api_endpoint', e.target.value)} 
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>API Key (optional)</Label>
                                <Input 
                                    type="password" 
                                    placeholder="Bearer Token" 
                                    disabled={readOnly}
                                    value={config.final_api_key} 
                                    onChange={(e) => updateField('final_api_key', e.target.value)} 
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Modell</Label>
                                <Input 
                                    placeholder="large-v3-turbo" 
                                    disabled={readOnly}
                                    value={config.final_api_model} 
                                    onChange={(e) => updateField('final_api_model', e.target.value)} 
                                />
                            </div>
                            <div className="flex gap-2 pt-2">
                                <Button
                                    variant="outline"
                                    onClick={() => testAsr('final')}
                                    disabled={finalTest.status === 'testing' || readOnly}
                                    className="gap-2"
                                >
                                    {finalTest.status === 'testing' && <Loader2 className="w-4 h-4 animate-spin" />}
                                    Verbindung testen
                                </Button>
                            </div>
                            {finalTest.result && (
                                <div className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${
                                    finalTest.result.ok
                                        ? 'border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-300'
                                        : 'border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300'
                                }`}>
                                    {finalTest.result.ok
                                        ? <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
                                        : <XCircle className="w-4 h-4 mt-0.5 shrink-0" />}
                                    <span>{finalTest.result.message}</span>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="quality">
                    <Card>
                        <CardHeader>
                            <CardTitle>Qualität & Anti-Halluzination</CardTitle>
                            <CardDescription>
                                Verhindert erfundene Füllwörter bei Stille. Werden an den
                                Whisper-Server übergeben.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="vad-filter">VAD-Filter (Stille entfernen)</Label>
                                <Switch
                                    id="vad-filter"
                                    checked={config.vad_filter}
                                    disabled={readOnly}
                                    onCheckedChange={(checked) => updateField('vad_filter', checked)}
                                />
                            </div>
                            <div className="flex items-center justify-between">
                                <Label htmlFor="cond-prev">Auf vorherigen Text bedingen</Label>
                                <Switch
                                    id="cond-prev"
                                    checked={config.condition_on_previous_text}
                                    disabled={readOnly}
                                    onCheckedChange={(checked) => updateField('condition_on_previous_text', checked)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>VAD min. Stille (ms)</Label>
                                <Input
                                    type="number" min={0} max={5000} step={50}
                                    disabled={readOnly}
                                    value={config.vad_min_silence_ms}
                                    onChange={(e) => updateField('vad_min_silence_ms', parseInt(e.target.value) || 0)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Temperatur (0 = deterministisch)</Label>
                                <Input
                                    type="number" min={0} max={1} step={0.1}
                                    disabled={readOnly}
                                    value={config.temperature}
                                    onChange={(e) => updateField('temperature', parseFloat(e.target.value) || 0)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>No-Speech-Schwelle</Label>
                                <Input
                                    type="number" min={0} max={1} step={0.05}
                                    disabled={readOnly}
                                    value={config.no_speech_threshold}
                                    onChange={(e) => updateField('no_speech_threshold', parseFloat(e.target.value) || 0)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Compression-Ratio-Schwelle</Label>
                                <Input
                                    type="number" min={0} max={10} step={0.1}
                                    disabled={readOnly}
                                    value={config.compression_ratio_threshold}
                                    onChange={(e) => updateField('compression_ratio_threshold', parseFloat(e.target.value) || 0)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Log-Prob-Schwelle</Label>
                                <Input
                                    type="number" min={-10} max={0} step={0.1}
                                    disabled={readOnly}
                                    value={config.log_prob_threshold}
                                    onChange={(e) => updateField('log_prob_threshold', parseFloat(e.target.value) || 0)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Halluzinations-Stille-Schwelle (Sek., optional)</Label>
                                <Input
                                    type="number" min={0} max={60} step={0.5}
                                    placeholder="aus"
                                    disabled={readOnly}
                                    value={config.hallucination_silence_threshold ?? ''}
                                    onChange={(e) => updateField('hallucination_silence_threshold', e.target.value === '' ? null : parseFloat(e.target.value))}
                                />
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Beam-Size Live</Label>
                                    <Input
                                        type="number" min={1} max={10}
                                        disabled={readOnly}
                                        value={config.live_beam_size}
                                        onChange={(e) => updateField('live_beam_size', parseInt(e.target.value) || 1)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>Beam-Size Final</Label>
                                    <Input
                                        type="number" min={1} max={10}
                                        disabled={readOnly}
                                        value={config.final_beam_size}
                                        onChange={(e) => updateField('final_beam_size', parseInt(e.target.value) || 5)}
                                    />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            <Button onClick={saveConfig} disabled={readOnly} className="w-full">Einstellungen speichern</Button>
        </div>
    );
};

export default WhisperConfig;
