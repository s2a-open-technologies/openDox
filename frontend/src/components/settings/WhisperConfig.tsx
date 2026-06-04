import { useState, useEffect } from 'react';
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
}

const WhisperConfig = () => {
    const { authFetch } = useAuth();
    const [config, setConfig] = useState<WhisperSettings>({
        live_backend: 'api',
        live_api_endpoint: '',
        live_api_key: '',
        live_api_model: 'whisper-1',
        final_backend: 'api',
        final_api_endpoint: '',
        final_api_key: '',
        final_api_model: 'whisper-1',
        language: 'de',
        chunk_length_s: 3,
        overlap_s: 0,
    });

    useEffect(() => {
        authFetch('/api/v1/settings/whisper-settings/')
            .then(res => res.json())
            .then((data: any) => {
                setConfig({
                    live_backend: data.live_backend || 'api',
                    live_api_endpoint: data.live_api_endpoint || '',
                    live_api_key: data.live_api_key || '',
                    live_api_model: data.live_api_model || 'whisper-1',
                    final_backend: data.final_backend || 'api',
                    final_api_endpoint: data.final_api_endpoint || '',
                    final_api_key: data.final_api_key || '',
                    final_api_model: data.final_api_model || 'whisper-1',
                    language: data.language || 'de',
                    chunk_length_s: data.chunk_length_s ?? 3,
                    overlap_s: data.overlap_s ?? 0,
                });
            })
            .catch(console.error);
    }, []);

    const updateField = (key: keyof WhisperSettings, value: any) => {
        setConfig(prev => ({ ...prev, [key]: value }));
    };

    const saveConfig = async () => {
        await authFetch('/api/v1/settings/whisper-settings/', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
    };

    return (
        <div className="space-y-4">
            <h3 className="text-lg font-medium">Transkriptionsserver Konfiguration</h3>
            
            <Tabs defaultValue="general" className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="general">Allgemein</TabsTrigger>
                    <TabsTrigger value="live">Live</TabsTrigger>
                    <TabsTrigger value="final">Final</TabsTrigger>
                </TabsList>

                <TabsContent value="general">
                    <Card>
                        <CardHeader>
                            <CardTitle>Allgemeine Einstellungen</CardTitle>
                            <CardDescription>Sprache und Chunk-Verhalten</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label>Sprache</Label>
                                <Select value={config.language} onValueChange={(v) => updateField('language', v)}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Wählen..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="de">Deutsch</SelectItem>
                                        <SelectItem value="en">Englisch</SelectItem>
                                        <SelectItem value="fr">Französisch</SelectItem>
                                        <SelectItem value="es">Spanisch</SelectItem>
                                        <SelectItem value="it">Italienisch</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>Chunk-Länge (Sekunden)</Label>
                                <Input 
                                    type="number" 
                                    min={1} 
                                    max={10} 
                                    value={config.chunk_length_s} 
                                    onChange={(e) => updateField('chunk_length_s', parseInt(e.target.value) || 3)} 
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Überlappung (Sekunden)</Label>
                                <Input 
                                    type="number" 
                                    min={0} 
                                    max={2} 
                                    value={config.overlap_s} 
                                    onChange={(e) => updateField('overlap_s', parseInt(e.target.value) || 0)} 
                                />
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
                                <Switch 
                                    id="live-enabled" 
                                    checked={config.live_backend !== 'disabled'} 
                                    onCheckedChange={(checked) => updateField('live_backend', checked ? 'api' : 'disabled')} 
                                />
                            </div>
                            
                            {config.live_backend !== 'disabled' && (
                                <>
                                    <div className="space-y-2">
                                        <Label>API Endpoint</Label>
                                        <Input 
                                            placeholder="http://localhost:9000" 
                                            value={config.live_api_endpoint} 
                                            onChange={(e) => updateField('live_api_endpoint', e.target.value)} 
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>API Key (optional)</Label>
                                        <Input 
                                            type="password" 
                                            placeholder="Bearer Token" 
                                            value={config.live_api_key} 
                                            onChange={(e) => updateField('live_api_key', e.target.value)} 
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Modell</Label>
                                        <Input 
                                            placeholder="whisper-1" 
                                            value={config.live_api_model} 
                                            onChange={(e) => updateField('live_api_model', e.target.value)} 
                                        />
                                    </div>
                                </>
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
                                    value={config.final_api_endpoint} 
                                    onChange={(e) => updateField('final_api_endpoint', e.target.value)} 
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>API Key (optional)</Label>
                                <Input 
                                    type="password" 
                                    placeholder="Bearer Token" 
                                    value={config.final_api_key} 
                                    onChange={(e) => updateField('final_api_key', e.target.value)} 
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Modell</Label>
                                <Input 
                                    placeholder="whisper-1" 
                                    value={config.final_api_model} 
                                    onChange={(e) => updateField('final_api_model', e.target.value)} 
                                />
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            <Button onClick={saveConfig} className="w-full">Einstellungen speichern</Button>
        </div>
    );
};

export default WhisperConfig;
