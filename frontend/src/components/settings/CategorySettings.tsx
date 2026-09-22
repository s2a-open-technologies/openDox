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
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

interface CategorySettingsData {
    id?: number;
    name: string;
    description: string;
    system_prompt: string;
    whisper_prompt: string | null;
    llm_override_enabled: boolean;
    llm_model: string | null;
    llm_api_endpoint: string | null;
    llm_api_key: string | null;
    llm_temperature: number | null;
    llm_max_tokens: number | null;
    llm_top_p: number | null;
    llm_frequency_penalty: number | null;
    llm_enable_thinking: boolean | null;
    user_id?: number | null;
}

const emptyForm = (): CategorySettingsData => ({
    name: '',
    description: '',
    system_prompt: '',
    whisper_prompt: null,
    llm_override_enabled: false,
    llm_model: null,
    llm_api_endpoint: null,
    llm_api_key: null,
    llm_temperature: null,
    llm_max_tokens: null,
    llm_top_p: null,
    llm_frequency_penalty: null,
    llm_enable_thinking: null,
});

const CategorySettings = () => {
    const { user, authFetch } = useAuth();
    const isPrivileged = user?.role === 'admin' || user?.role === 'moderator' || user?.role === 'demo_viewer';
    const [categories, setCategories] = useState<CategorySettingsData[]>([]);
    const [settings, setSettings] = useState<CategorySettingsData>(emptyForm());
    const [loading, setLoading] = useState(false);
    const [isEditing, setIsEditing] = useState(false);

    const canManage = (category: CategorySettingsData) =>
        category.user_id != null ? category.user_id === user?.id || user?.role === 'admin' : isPrivileged;

    const fetchCategories = async () => {
        try {
            const res = await authFetch('/api/v1/settings/categories/');
            if (res.ok) {
                const data = await res.json();
                setCategories(data);
            }
        } catch (error) {
            console.error('Failed to fetch categories:', error);
        }
    };

    useEffect(() => {
        fetchCategories();
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            const url = isEditing && settings.id
                ? `/api/v1/settings/categories/${settings.id}`
                : '/api/v1/settings/categories/';

            const method = isEditing && settings.id ? 'PUT' : 'POST';

            // When override is disabled, clear the LLM fields before sending
            const payload = settings.llm_override_enabled
                ? settings
                : {
                    ...settings,
                    llm_model: null,
                    llm_api_endpoint: null,
                    llm_api_key: null,
                    llm_temperature: null,
                    llm_max_tokens: null,
                    llm_top_p: null,
                    llm_frequency_penalty: null,
                    llm_enable_thinking: null,
                };

            const res = await authFetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (res.ok) {
                toast.success(isEditing ? 'Kategorie aktualisiert' : 'Kategorie erstellt');
                await fetchCategories();
                resetForm();
            } else {
                const err = await res.json().catch(() => ({}));
                toast.error(err.detail || 'Speichern fehlgeschlagen');
            }
        } catch (error) {
            console.error(error);
            toast.error('Verbindungsfehler');
        } finally {
            setLoading(false);
        }
    };

    const handleEdit = (category: CategorySettingsData) => {
        setSettings(category);
        setIsEditing(true);
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Möchten Sie diese Kategorie wirklich löschen?')) return;

        try {
            const res = await authFetch(`/api/v1/settings/categories/${id}`, {
                method: 'DELETE',
            });

            if (res.ok) {
                toast.success('Kategorie gelöscht');
                await fetchCategories();
                if (settings.id === id) {
                    resetForm();
                }
            } else {
                toast.error('Löschen fehlgeschlagen');
            }
        } catch (error) {
            console.error('Failed to delete category:', error);
            toast.error('Verbindungsfehler');
        }
    };

    const resetForm = () => {
        setSettings(emptyForm());
        setIsEditing(false);
    };

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Kategorien Liste</CardTitle>
                    <CardDescription>Verwalten Sie Ihre vorhandenen Kategorien</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        {categories.map((category) => (
                            <div
                                key={category.id}
                                className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                            >
                                <div className="space-y-1">
                                    <div className="flex items-center gap-2">
                                        <div className="font-medium">{category.name}</div>
                                        <span className="text-[10px] uppercase tracking-wide rounded-full border px-2 py-0.5 text-muted-foreground">
                                            {category.user_id == null ? 'Global' : 'Eigene Kategorie'}
                                        </span>
                                    </div>
                                    <div className="text-sm text-muted-foreground">{category.description}</div>
                                    {category.llm_override_enabled && category.llm_model && (
                                        <div className="text-xs text-blue-500">
                                            LLM: {category.llm_model}
                                        </div>
                                    )}
                                </div>
                                {canManage(category) && (
                                    <div className="flex gap-2">
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            onClick={() => handleEdit(category)}
                                        >
                                            <Pencil className="h-4 w-4" />
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="text-destructive hover:text-destructive"
                                            onClick={() => category.id && handleDelete(category.id)}
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    </div>
                                )}
                            </div>
                        ))}
                        {categories.length === 0 && (
                            <div className="text-center text-muted-foreground py-8">
                                Keine Kategorien vorhanden
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>
            <Card>
                <CardHeader>
                    <CardTitle>{isEditing ? 'Kategorie bearbeiten' : 'Neue Kategorie erstellen'}</CardTitle>
                    <CardDescription>
                        {isEditing ? 'Bearbeiten Sie die ausgewählte Kategorie' : 'Fügen Sie eine neue Kategorie hinzu'}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Kategorie Name</Label>
                                <Input
                                    value={settings.name}
                                    onChange={e => setSettings({ ...settings, name: e.target.value })}
                                    placeholder="Kategorie Name"
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Beschreibung</Label>
                                <Input
                                    value={settings.description}
                                    onChange={e => setSettings({ ...settings, description: e.target.value })}
                                    placeholder="Beschreibung"
                                    required
                                />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label>System Prompt (LLM)</Label>
                            <Textarea
                                value={settings.system_prompt}
                                onChange={e => setSettings({ ...settings, system_prompt: e.target.value })}
                                placeholder="Anweisungen für die Zusammenfassung, z.B. Format, Struktur, Fokus..."
                                className="min-h-[100px]"
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Transkriptions-Hint (Whisper)</Label>
                            <Textarea
                                value={settings.whisper_prompt ?? ''}
                                onChange={e => setSettings({ ...settings, whisper_prompt: e.target.value || null })}
                                placeholder="Kardiologie, Echokardiographie, Sinusbradykardie, Dr. Müller, EKG, Herzinsuffizienz ..."
                                className="min-h-[80px]"
                            />
                            <p className="text-xs text-muted-foreground">
                                Fachvokabular für die Spracherkennung. Kommagetrennte Begriffe helfen Whisper Fachbegriffe korrekt zu erkennen. Optional.
                            </p>
                        </div>

                        {isPrivileged && (
                        <div className="border rounded-lg p-4 space-y-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <Label className="text-base">Eigenes LLM verwenden</Label>
                                    <p className="text-sm text-muted-foreground">
                                        Überschreibt die globalen LLM-Einstellungen für diese Kategorie
                                    </p>
                                </div>
                                <Switch
                                    checked={settings.llm_override_enabled}
                                    onCheckedChange={(checked) =>
                                        setSettings({ ...settings, llm_override_enabled: checked })
                                    }
                                />
                            </div>

                            {settings.llm_override_enabled && (
                                <div className="space-y-4 pt-2 border-t">
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>Modell</Label>
                                            <Input
                                                value={settings.llm_model ?? ''}
                                                onChange={e => setSettings({ ...settings, llm_model: e.target.value || null })}
                                                placeholder="z.B. deepseek-r1:14b"
                                                required
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>API Endpunkt</Label>
                                            <Input
                                                value={settings.llm_api_endpoint ?? ''}
                                                onChange={e => setSettings({ ...settings, llm_api_endpoint: e.target.value || null })}
                                                placeholder="http://localhost:11434/v1"
                                            />
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>API Key</Label>
                                        <Input
                                            value={settings.llm_api_key ?? ''}
                                            onChange={e => setSettings({ ...settings, llm_api_key: e.target.value || null })}
                                            placeholder="Optional"
                                            type="password"
                                        />
                                    </div>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>Temperature</Label>
                                            <Input
                                                type="number"
                                                min={0}
                                                max={1}
                                                step={0.1}
                                                value={settings.llm_temperature ?? ''}
                                                onChange={e => setSettings({
                                                    ...settings,
                                                    llm_temperature: e.target.value ? parseFloat(e.target.value) : null,
                                                })}
                                                placeholder="Standard aus globalen Einstellungen"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Max Tokens</Label>
                                            <Input
                                                type="number"
                                                min={128}
                                                max={32768}
                                                step={128}
                                                value={settings.llm_max_tokens ?? ''}
                                                onChange={e => setSettings({
                                                    ...settings,
                                                    llm_max_tokens: e.target.value ? parseInt(e.target.value) : null,
                                                })}
                                                placeholder="Standard aus globalen Einstellungen"
                                            />
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>Top P</Label>
                                            <Input
                                                type="number"
                                                min={0}
                                                max={1}
                                                step={0.1}
                                                value={settings.llm_top_p ?? ''}
                                                onChange={e => setSettings({
                                                    ...settings,
                                                    llm_top_p: e.target.value ? parseFloat(e.target.value) : null,
                                                })}
                                                placeholder="Standard aus globalen Einstellungen"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Frequency Penalty</Label>
                                            <Input
                                                type="number"
                                                min={-2}
                                                max={2}
                                                step={0.1}
                                                value={settings.llm_frequency_penalty ?? ''}
                                                onChange={e => setSettings({
                                                    ...settings,
                                                    llm_frequency_penalty: e.target.value ? parseFloat(e.target.value) : null,
                                                })}
                                                placeholder="Standard aus globalen Einstellungen"
                                            />
                                        </div>
                                    </div>
                                    <div className="space-y-4 pt-2 border-t">
                                        <div className="flex items-center gap-3">
                                            <Switch
                                                id={`cat-enable-thinking-${settings.id ?? 'new'}`}
                                                checked={settings.llm_enable_thinking ?? false}
                                                onCheckedChange={(checked) =>
                                                    setSettings({ ...settings, llm_enable_thinking: checked })
                                                }
                                            />
                                            <Label htmlFor={`cat-enable-thinking-${settings.id ?? 'new'}`}>
                                                Thinking aktivieren
                                            </Label>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                        )}

                        <div className="flex gap-2">
                            <Button type="submit" disabled={loading}>
                                {loading ? 'Speichern...' : (isEditing ? 'Aktualisieren' : 'Erstellen')}
                            </Button>
                            {isEditing && (
                                <Button type="button" variant="outline" onClick={resetForm}>
                                    Abbrechen
                                </Button>
                            )}
                        </div>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
};

export default CategorySettings;
