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

import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from '@/contexts/AuthContext';

interface LlmSettings {
    llm_api_endpoint: string;
    llm_api_key: string;
    llm_model: string;
    llm_temperature: number;
    llm_max_tokens: number;
    correction_model: string;
}

const LlmConfig = () => {
    const { authFetch } = useAuth();
    const [config, setConfig] = useState<LlmSettings>({
        llm_api_endpoint: 'http://localhost:11434/v1',
        llm_api_key: '',
        llm_model: 'medgemma-4b-it:Q4_K_M',
        llm_temperature: 0.2,
        llm_max_tokens: 2048,
        correction_model: '',
    });

    useEffect(() => {
        authFetch('/api/v1/settings/llm-settings/')
            .then(res => res.json())
            .then((data: any) => {
                setConfig({
                    llm_api_endpoint: data.llm_api_endpoint || 'http://localhost:11434/v1',
                    llm_api_key: data.llm_api_key || '',
                    llm_model: data.llm_model || 'medgemma-4b-it:Q4_K_M',
                    llm_temperature: data.llm_temperature ?? 0.2,
                    llm_max_tokens: data.llm_max_tokens ?? 2048,
                    correction_model: data.correction_model || '',
                });
            })
            .catch(console.error);
    }, []);

    const updateField = (key: keyof LlmSettings, value: any) => {
        setConfig(prev => ({ ...prev, [key]: value }));
    };

    const saveConfig = async () => {
        await authFetch('/api/v1/settings/llm-settings/', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
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
                            value={config.llm_api_key} 
                            onChange={(e) => updateField('llm_api_key', e.target.value)} 
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>Modell</Label>
                        <Input 
                            placeholder="medgemma-4b-it:Q4_K_M" 
                            value={config.llm_model} 
                            onChange={(e) => updateField('llm_model', e.target.value)} 
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>Korrektions-Modell (optional)</Label>
                        <Input
                            placeholder="leer = gleich wie Zusammenfassungs-Modell"
                            value={config.correction_model}
                            onChange={(e) => updateField('correction_model', e.target.value)}
                        />
                        <p className="text-xs text-muted-foreground">
                            Kleines schnelles Modell für Near-Live-Korrektur bie Verwendung von Whisper, z.B. qwen2.5:0.5b
                        </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>Temperatur (0.0 - 1.0)</Label>
                            <Input 
                                type="number" 
                                min={0} 
                                max={1} 
                                step={0.1}
                                value={config.llm_temperature} 
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
                                onChange={(e) => updateField('llm_max_tokens', parseInt(e.target.value))} 
                            />
                        </div>
                    </div>
                </CardContent>
            </Card>

            <Button onClick={saveConfig} className="w-full">Einstellungen speichern</Button>
        </div>
    );
};

export default LlmConfig;
