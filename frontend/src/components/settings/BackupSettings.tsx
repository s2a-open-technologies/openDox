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

import { useRef, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Download, Upload, Loader2, FileJson } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'sonner';

const BackupSettings = ({ readOnly = false }: { readOnly?: boolean }) => {
    const { authFetch } = useAuth();
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const [exporting, setExporting] = useState(false);
    const [importing, setImporting] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    const handleExport = async () => {
        setExporting(true);
        try {
            const res = await authFetch('/api/v1/settings/backup/');
            if (!res.ok) {
                throw new Error('Export fehlgeschlagen');
            }
            const blob = await res.blob();
            const disposition = res.headers.get('content-disposition') || '';
            const match = disposition.match(/filename="?([^"]+)"?/);
            const filename = match ? match[1] : `opendox-backup-${Date.now()}.json`;
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            toast.success('Backup heruntergeladen');
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Export fehlgeschlagen');
        } finally {
            setExporting(false);
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0] ?? null;
        setSelectedFile(file);
    };

    const handleImport = async () => {
        if (!selectedFile) {
            toast.error('Bitte zuerst eine Datei auswählen');
            return;
        }
        setImporting(true);
        try {
            const formData = new FormData();
            formData.append('file', selectedFile);
            const res = await authFetch('/api/v1/settings/backup/restore/', {
                method: 'POST',
                body: formData,
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || 'Wiederherstellung fehlgeschlagen');
            }
            const data = await res.json();
            toast.success(`Wiederhergestellt: ${(data.restored || []).join(', ')}`);
            setSelectedFile(null);
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Wiederherstellung fehlgeschlagen');
        } finally {
            setImporting(false);
        }
    };

    return (
        <div className="space-y-4">
            <Card>
                <CardHeader>
                    <CardTitle>Export</CardTitle>
                    <CardDescription>
                        Alle Einstellungen als JSON-Datei sichern (Whisper, LLM, LDAP, Kategorien, Sprachen, Terminologie)
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Button onClick={handleExport} disabled={exporting || readOnly} className="gap-2">
                        {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                        Backup herunterladen
                    </Button>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Wiederherstellung</CardTitle>
                    <CardDescription>
                        Einstellungen aus einer Backup-Datei einspielen. Überschreibt alle aktuellen Werte.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="application/json,.json"
                        disabled={readOnly}
                        onChange={handleFileSelect}
                        className="hidden"
                    />
                    {selectedFile ? (
                        <div className="flex items-center justify-between gap-2 p-3 border rounded-md bg-muted/30">
                            <div className="flex items-center gap-2 text-sm">
                                <FileJson className="w-4 h-4 text-primary" />
                                <span className="font-medium">{selectedFile.name}</span>
                                <span className="text-muted-foreground">
                                    {(selectedFile.size / 1024).toFixed(1)} KB
                                </span>
                            </div>
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                disabled={readOnly}
                                onClick={() => {
                                    setSelectedFile(null);
                                    if (fileInputRef.current) fileInputRef.current.value = '';
                                }}
                            >
                                Entfernen
                            </Button>
                        </div>
                    ) : (
                        <Button
                            type="button"
                            variant="outline"
                            className="w-full gap-2"
                            disabled={readOnly}
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <Upload className="w-4 h-4" />
                            Datei auswählen
                        </Button>
                    )}
                    <Button
                        onClick={handleImport}
                        disabled={importing || !selectedFile || readOnly}
                        className="gap-2"
                    >
                        {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                        Backup einspielen
                    </Button>
                </CardContent>
            </Card>
        </div>
    );
};

export default BackupSettings;