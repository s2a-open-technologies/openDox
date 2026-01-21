import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useAuth } from '@/contexts/AuthContext';

interface WhisperSettings {
    model_size: string;
    device: string;
    compute_type: string;
}

const WhisperConfig = () => {
    const { authFetch } = useAuth();
    const [config, setConfig] = useState<WhisperSettings>({
        model_size: 'base',
        device: 'cpu',
        compute_type: 'int8'
    });

    useEffect(() => {
        authFetch('/api/v1/settings/whisper-settings/')
            .then(res => res.json())
            .then(data => setConfig(data))
            .catch(console.error);
    }, []);

    const saveConfig = async () => {
        await authFetch('/api/v1/settings/whisper-settings/', {
            method: 'PUT',
            body: JSON.stringify(config)
        });
    };

    return (
        <div className="space-y-4">
            <h3 className="text-lg font-medium">Whisper Konfiguration</h3>
            <div className="grid gap-4">
                <div className="space-y-2">
                    <Label>Modell Größe</Label>
                    <Select
                        value={config.model_size}
                        onValueChange={(val) => setConfig({ ...config, model_size: val })}
                    >
                        <SelectTrigger>
                            <SelectValue placeholder="Wählen..." />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="tiny">Tiny (Schnell, ungenau)</SelectItem>
                            <SelectItem value="base">Base (Balanced)</SelectItem>
                            <SelectItem value="small">Small (Genauer)</SelectItem>
                            <SelectItem value="medium">Medium (Langsam, sehr genau)</SelectItem>
                            <SelectItem value="large-v3">Large v3 (Beste Qualität, sehr langsam)</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                <div className="space-y-2">
                    <Label>Gerät</Label>
                    <Select
                        value={config.device}
                        onValueChange={(val) => setConfig({ ...config, device: val })}
                    >
                        <SelectTrigger>
                            <SelectValue placeholder="Wählen..." />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="cpu">CPU</SelectItem>
                            <SelectItem value="cuda">GPU (CUDA)</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                <Button onClick={saveConfig}>Einstellungen speichern</Button>
            </div>
        </div>
    );
};

export default WhisperConfig;
