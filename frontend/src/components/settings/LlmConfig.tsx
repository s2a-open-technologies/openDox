/*
  openDox - Medical transcription platform
  Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
  SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
  SPDX-License-Identifier: AGPL-3.0-or-later

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

import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from '@/contexts/AuthContext';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

interface LlmSettings {
    llm_api_endpoint: string;
    llm_api_key: string;
    llm_model: string;
    llm_temperature: number;
    llm_max_tokens: number;
    llm_top_p: number;
    llm_frequency_penalty: number;
    llm_enable_thinking: boolean;
    correction_model: string;
    sanitizer_enabled: boolean;
    sanitizer_endpoint: string;
    sanitizer_api_key: string;
}

type LlmSettingsResponse = Partial<LlmSettings>;

const LlmConfig = ({ readOnly = false }: { readOnly?: boolean }) => {
    const { authFetch } = useAuth();
    const [testStatus, setTestStatus] = useState<{ ok: boolean; message: string } | null>(null);
    const [testing, setTesting] = useState(false);

    const [config, setConfig] = useState<LlmSettings>({
        llm_api_endpoint: 'http://localhost:11434/v1',
        llm_api_key: '',
        llm_model: 'medgemma-4b-it:Q4_K_M',
        llm_temperature: 0.2,
        llm_max_tokens: 2048,
        llm_top_p: 0.9,
        llm_frequency_penalty: 0.3,
        llm_enable_thinking: false,
        correction_model: '',
        sanitizer_enabled: false,
        sanitizer_endpoint: '',
        sanitizer_api_key: '',
    });

    useEffect(() => {
        authFetch('/api/v1/settings/llm-settings/')
            .then(res => res.json())
            .then((data: LlmSettingsResponse) => {
                setConfig({
                    llm_api_endpoint: data.llm_api_endpoint || 'http://localhost:11434/v1',
                    llm_api_key: data.llm_api_key || '',
                    llm_model: data.llm_model || 'medgemma-4b-it:Q4_K_M',
                    llm_temperature: data.llm_temperature ?? 0.2,
                    llm_max_tokens: data.llm_max_tokens ?? 2048,
                    llm_top_p: data.llm_top_p ?? 0.9,
                    llm_frequency_penalty: data.llm_frequency_penalty ?? 0.3,
                    llm_enable_thinking: data.llm_enable_thinking ?? false,
                    correction_model: data.correction_model || '',
                    sanitizer_enabled: data.sanitizer_enabled ?? false,
                    sanitizer_endpoint: data.sanitizer_endpoint || '',
                    sanitizer_api_key: data.sanitizer_api_key || '',
                });
            })
            .catch(console.error);
    }, []);

    const updateField = (key: keyof LlmSettings, value: LlmSettings[keyof LlmSettings]) => {
        setConfig(prev => ({ ...prev, [key]: value }));
    };

    const saveConfig = async () => {
        try {
            const res = await authFetch('/api/v1/settings/llm-settings/', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
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

    const testConnection = async () => {
        setTesting(true);
        setTestStatus(null);
        try {
            const res = await authFetch('/api/v1/settings/llm-test/');
            const data = await res.json();
            if (data.ok) {
                const reply = data.reply ? `„${data.reply}"` : 'keine Antwort erhalten';
                setTestStatus({ ok: true, message: `Verbunden · Antwort: ${reply}` });
            } else {
                setTestStatus({ ok: false, message: data.error || 'Unbekannter Fehler' });
            }
        } catch {
            setTestStatus({ ok: false, message: 'Anfrage fehlgeschlagen' });
        } finally {
            setTesting(false);
        }
    };

    return (
        <div className="space-y-4">
            <Card>
                <CardHeader>
                    <CardTitle>LLM / Ollama Konfiguration</CardTitle>
                    <CardDescription>
                        Konfiguration für Textgenerierung und Zusammenfassung
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2">
                        <Label>API Endpoint</Label>
                        <Input 
                            placeholder="http://localhost:11434/v1" 
                            disabled={readOnly}
                            value={config.llm_api_endpoint} 
                            onChange={(e) => updateField('llm_api_endpoint', e.target.value)} 
                        />
                        <p className="text-xs text-muted-foreground">
                            Ollama, vLLM, oder jeder OpenAI-kompatible Endpoint
                        </p>
                    </div>

                    <div className="space-y-2">
                        <Label>API Key (optional)</Label>
                        <Input 
                            type="password" 
                            placeholder="sk-..." 
                            disabled={readOnly}
                            value={config.llm_api_key} 
                            onChange={(e) => updateField('llm_api_key', e.target.value)} 
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>Modell</Label>
                        <Input 
                            placeholder="medgemma-4b-it:Q4_K_M" 
                            disabled={readOnly}
                            value={config.llm_model} 
                            onChange={(e) => updateField('llm_model', e.target.value)} 
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>Korrektions-Modell (optional)</Label>
                        <Input
                            placeholder="leer = gleich wie Zusammenfassungs-Modell"
                            disabled={readOnly}
                            value={config.correction_model}
                            onChange={(e) => updateField('correction_model', e.target.value)}
                        />
                        <p className="text-xs text-muted-foreground">
                            Kleines schnelles Modell für Live-Ansicht-Korrektur bei Verwendung von Whisper für Near-Live, z.B. qwen2.5:0.5b
                        </p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>Temperatur (0.0 - 1.0)</Label>
                            <Input 
                                type="number" 
                                min={0} 
                                max={1} 
                                step={0.1}
                                value={config.llm_temperature} 
                                disabled={readOnly}
                                onChange={(e) => updateField('llm_temperature', parseFloat(e.target.value))} 
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Max Tokens</Label>
                            <Input
                                type="number"
                                min={128}
                                max={8192}
                                step={128}
                                value={config.llm_max_tokens}
                                disabled={readOnly}
                                onChange={(e) => updateField('llm_max_tokens', parseInt(e.target.value))}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Top P (0.0 - 1.0)</Label>
                            <Input
                                type="number"
                                min={0}
                                max={1}
                                step={0.1}
                                value={config.llm_top_p}
                                disabled={readOnly}
                                onChange={(e) => updateField('llm_top_p', parseFloat(e.target.value))}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Frequency Penalty (-2.0 - 2.0)</Label>
                            <Input
                                type="number"
                                min={-2}
                                max={2}
                                step={0.1}
                                value={config.llm_frequency_penalty}
                                disabled={readOnly}
                                onChange={(e) => updateField('llm_frequency_penalty', parseFloat(e.target.value))}
                            />
                        </div>
                    </div>

                    <div className="space-y-4 border-t pt-4">
                        <div className="flex items-center gap-3">
                            <Switch
                                id="llm-enable-thinking"
                                checked={config.llm_enable_thinking}
                                disabled={readOnly}
                                onCheckedChange={(v) => updateField('llm_enable_thinking', v)}
                            />
                            <Label htmlFor="llm-enable-thinking">Thinking aktivieren</Label>
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Standardmäßig deaktiviert: Reasoning-Modelle (z.B. MedGemma, Qwen3, DeepSeek-R1)
                            können bei Zusammenfassungen sonst extrem lange brauchen oder hängen bleiben.
                        </p>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>PII-Sanitizer</CardTitle>
                    <CardDescription>
                        Anonymisiert sensible Daten im Transkript bevor sie an das LLM gesendet werden
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center gap-3">
                        <Switch
                            id="sanitizer-enabled"
                            checked={config.sanitizer_enabled}
                            disabled={readOnly}
                            onCheckedChange={(v) => updateField('sanitizer_enabled', v)}
                        />
                        <Label htmlFor="sanitizer-enabled">Sanitizer aktivieren</Label>
                    </div>

                    {config.sanitizer_enabled && (
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <Label>Sanitizer Endpoint (vollständige URL)</Label>
                                <Input
                                    placeholder="http://entityguard:9500/api/v1/sanitize"
                                    disabled={readOnly}
                                    value={config.sanitizer_endpoint}
                                    onChange={(e) => updateField('sanitizer_endpoint', e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>API Key (optional)</Label>
                                <Input
                                    type="password"
                                    placeholder="Bearer Token"
                                    disabled={readOnly}
                                    value={config.sanitizer_api_key}
                                    onChange={(e) => updateField('sanitizer_api_key', e.target.value)}
                                />
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            <div className="flex gap-2">
                <Button onClick={saveConfig} disabled={readOnly} className="flex-1">Einstellungen speichern</Button>
                <Button onClick={testConnection} variant="outline" disabled={testing || readOnly} className="gap-2">
                    {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    Verbindung testen
                </Button>
            </div>

            {testStatus && (
                <div className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${
                    testStatus.ok
                        ? 'border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-300'
                        : 'border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300'
                }`}>
                    {testStatus.ok
                        ? <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
                        : <XCircle className="w-4 h-4 mt-0.5 shrink-0" />}
                    <span>{testStatus.message}</span>
                </div>
            )}
        </div>
    );
};

export default LlmConfig;
