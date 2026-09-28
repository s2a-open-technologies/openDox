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
import { useAuth } from '@/contexts/AuthContext';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

interface PersonalGlossaryResponse {
    personal_glossary: string | null;
}

const PersonalDictionary = () => {
    const { authFetch } = useAuth();
    const [glossary, setGlossary] = useState('');
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        authFetch('/api/v1/settings/my-dictionary/')
            .then(res => res.json())
            .then((data: PersonalGlossaryResponse) => {
                setGlossary(data.personal_glossary ?? '');
            })
            .catch(console.error);
    }, []);

    const save = async () => {
        setLoading(true);
        try {
            const res = await authFetch('/api/v1/settings/my-dictionary/', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ personal_glossary: glossary || null }),
            });
            if (res.ok) {
                toast.success('Wörterbuch gespeichert');
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
                <CardTitle>Eigene Begriffe</CardTitle>
                <CardDescription>
                    Werden bei jeder Ihrer Aufnahmen automatisch phonetisch korrigiert — nur für
                    Sie sichtbar, auch nicht für Administratoren.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <Textarea
                    value={glossary}
                    onChange={e => setGlossary(e.target.value)}
                    placeholder="Sertralin, Metformin, Ibuprofen ..."
                    className="min-h-[120px]"
                />
                <p className="text-xs text-muted-foreground">
                    Komma-, Semikolon- oder zeilengetrennte Begriffe. Wird bei der finalen
                    Transkription mit dem Glossar des gewählten Profils zusammengeführt.
                </p>
                <Button onClick={save} disabled={loading}>
                    {loading ? 'Speichern...' : 'Speichern'}
                </Button>
            </CardContent>
        </Card>
    );
};

export default PersonalDictionary;
