/*
  openDox - Medical transcription platform
  Copyright (C) 2025  S2A Open Technologies gGmbH
  SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
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

import { useTranslation } from 'react-i18next';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { apiErrorMessage } from '@/lib/apiError';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Pencil, Plus, Trash2, Upload, X } from 'lucide-react';
import { toast } from 'sonner';

export interface DictionarySummary {
    id: number;
    name: string;
    user_id: number | null;
    term_count: number;
    category_ids: number[];
}

interface DictionaryDetail extends DictionarySummary {
    terms: string[];
}

// The term list is shown filtered and capped, so a whole ICD catalog
// (tens of thousands of lines) stays usable instead of freezing the dialog.
const MAX_VISIBLE_TERMS = 200;

interface DictionarySettingsProps {
    scope: 'global' | 'personal';
}

const DictionarySettings = ({ scope }: DictionarySettingsProps) => {
    const { t } = useTranslation(['dictionary', 'common']);
    const { user, authFetch } = useAuth();
    const [dictionaries, setDictionaries] = useState<DictionarySummary[]>([]);
    const [newName, setNewName] = useState('');
    const [detail, setDetail] = useState<DictionaryDetail | null>(null);
    const [draftName, setDraftName] = useState('');
    const [draftTerms, setDraftTerms] = useState<string[]>([]);
    const [search, setSearch] = useState('');
    const [newTerm, setNewTerm] = useState('');
    const [uploadMode, setUploadMode] = useState<'replace' | 'append'>('append');
    const [busy, setBusy] = useState(false);
    const fileInput = useRef<HTMLInputElement>(null);

    const inScope = (d: DictionarySummary) =>
        scope === 'global' ? d.user_id == null : d.user_id === user?.id;

    const fetchDictionaries = async () => {
        try {
            const res = await authFetch('/api/v1/settings/dictionaries/');
            if (!res.ok) throw new Error('Loading failed');
            const data: DictionarySummary[] = await res.json();
            setDictionaries(data.filter(inScope));
        } catch (error) {
            console.error(error);
            toast.error(t('loadFailed'));
        }
    };

    useEffect(() => {
        fetchDictionaries();
    }, [scope]);

    const openDictionary = async (id: number) => {
        try {
            const res = await authFetch(`/api/v1/settings/dictionaries/${id}`);
            if (!res.ok) throw new Error('Loading failed');
            const data: DictionaryDetail = await res.json();
            setDetail(data);
            setDraftName(data.name);
            setDraftTerms(data.terms);
            setSearch('');
            setNewTerm('');
        } catch (error) {
            console.error(error);
            toast.error(t('loadFailed'));
        }
    };

    const showError = async (res: Response, fallback: string) => {
        const body = await res.json().catch(() => ({}));
        toast.error(apiErrorMessage(body, fallback));
    };

    const create = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newName.trim()) return;
        setBusy(true);
        try {
            const res = await authFetch('/api/v1/settings/dictionaries/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newName.trim(), scope, terms: [] }),
            });
            if (!res.ok) return showError(res, t('common:saveFailed'));
            const created: DictionaryDetail = await res.json();
            setNewName('');
            toast.success(t('created'));
            await fetchDictionaries();
            await openDictionary(created.id);
        } catch {
            toast.error(t('common:connectionError'));
        } finally {
            setBusy(false);
        }
    };

    const remove = async (dictionary: DictionarySummary) => {
        const question = dictionary.category_ids.length > 0
            ? t('confirmDeleteUsed', { name: dictionary.name, count: dictionary.category_ids.length })
            : t('confirmDelete', { name: dictionary.name });
        if (!confirm(question)) return;
        try {
            const res = await authFetch(`/api/v1/settings/dictionaries/${dictionary.id}`, {
                method: 'DELETE',
            });
            if (!res.ok) return showError(res, t('deleteFailed'));
            toast.success(t('deleted'));
            if (detail?.id === dictionary.id) setDetail(null);
            await fetchDictionaries();
        } catch {
            toast.error(t('common:connectionError'));
        }
    };

    const isDirty = detail !== null && (
        draftName.trim() !== detail.name
        || draftTerms.length !== detail.terms.length
        || draftTerms.some((term, i) => term !== detail.terms[i])
    );

    const save = async () => {
        if (!detail) return;
        setBusy(true);
        try {
            const res = await authFetch(`/api/v1/settings/dictionaries/${detail.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: draftName.trim(), terms: draftTerms }),
            });
            if (!res.ok) return showError(res, t('common:saveFailed'));
            const saved: DictionaryDetail = await res.json();
            setDetail(saved);
            setDraftName(saved.name);
            setDraftTerms(saved.terms);
            toast.success(t('saved'));
            await fetchDictionaries();
        } catch {
            toast.error(t('common:connectionError'));
        } finally {
            setBusy(false);
        }
    };

    const addTerm = (e: React.FormEvent) => {
        e.preventDefault();
        const term = newTerm.trim();
        if (!term) return;
        if (draftTerms.some(existing => existing.toLowerCase() === term.toLowerCase())) {
            toast.info(t('termExists', { term }));
            return;
        }
        setDraftTerms([...draftTerms, term]);
        setNewTerm('');
    };

    const upload = async (file: File) => {
        if (!detail) return;
        if (isDirty && !confirm(t('uploadDiscardsChanges'))) return;
        setBusy(true);
        try {
            const form = new FormData();
            form.append('file', file);
            form.append('mode', uploadMode);
            const res = await authFetch(`/api/v1/settings/dictionaries/${detail.id}/upload`, {
                method: 'POST',
                body: form,
            });
            if (!res.ok) return showError(res, t('uploadFailed'));
            const result: DictionarySummary = await res.json();
            toast.success(t('uploaded', { count: result.term_count }));
            await fetchDictionaries();
            await openDictionary(detail.id);
        } catch {
            toast.error(t('common:connectionError'));
        } finally {
            setBusy(false);
            if (fileInput.current) fileInput.current.value = '';
        }
    };

    const filteredTerms = useMemo(() => {
        const needle = search.trim().toLowerCase();
        return needle
            ? draftTerms.filter(term => term.toLowerCase().includes(needle))
            : draftTerms;
    }, [draftTerms, search]);
    const visibleTerms = filteredTerms.slice(0, MAX_VISIBLE_TERMS);
    const hiddenCount = filteredTerms.length - visibleTerms.length;

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>{scope === 'global' ? t('globalTitle') : t('personalTitle')}</CardTitle>
                    <CardDescription>
                        {scope === 'global' ? t('globalDescription') : t('personalDescription')}
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <form onSubmit={create} className="flex gap-2">
                        <Input
                            value={newName}
                            onChange={e => setNewName(e.target.value)}
                            placeholder={t('newNamePlaceholder')}
                            aria-label={t('newNamePlaceholder')}
                        />
                        <Button type="submit" disabled={busy || !newName.trim()}>
                            <Plus className="h-4 w-4 mr-2" />
                            {t('create')}
                        </Button>
                    </form>
                    <div className="space-y-2">
                        {dictionaries.map(dictionary => (
                            <div
                                key={dictionary.id}
                                className={`flex items-center justify-between p-3 border rounded-lg transition-colors ${detail?.id === dictionary.id ? 'bg-accent' : 'hover:bg-accent/50'}`}
                            >
                                <div className="min-w-0">
                                    <div className="font-medium truncate">{dictionary.name}</div>
                                    <div className="text-xs text-muted-foreground">
                                        {t('termCount', { count: dictionary.term_count })}
                                        {' · '}
                                        {t('usedIn', { count: dictionary.category_ids.length })}
                                    </div>
                                </div>
                                <div className="flex gap-1 shrink-0">
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => openDictionary(dictionary.id)}
                                        aria-label={t('edit', { name: dictionary.name })}
                                    >
                                        <Pencil className="h-4 w-4" />
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="text-destructive hover:text-destructive"
                                        onClick={() => remove(dictionary)}
                                        aria-label={t('delete', { name: dictionary.name })}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        ))}
                        {dictionaries.length === 0 && (
                            <div className="text-center text-muted-foreground py-6">{t('empty')}</div>
                        )}
                    </div>
                    {scope === 'global' && (
                        <p className="text-xs text-muted-foreground">{t('attachHint')}</p>
                    )}
                </CardContent>
            </Card>

            {detail && (
                <Card>
                    <CardHeader>
                        <CardTitle>{detail.name}</CardTitle>
                        <CardDescription>{t('termCount', { count: draftTerms.length })}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="dictionary-name">{t('name')}</Label>
                            <Input
                                id="dictionary-name"
                                value={draftName}
                                onChange={e => setDraftName(e.target.value)}
                            />
                        </div>

                        <form onSubmit={addTerm} className="flex gap-2">
                            <Input
                                value={newTerm}
                                onChange={e => setNewTerm(e.target.value)}
                                placeholder={t('newTermPlaceholder')}
                                aria-label={t('newTermPlaceholder')}
                            />
                            <Button type="submit" variant="outline" disabled={!newTerm.trim()}>
                                <Plus className="h-4 w-4 mr-2" />
                                {t('addTerm')}
                            </Button>
                        </form>

                        <Input
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            placeholder={t('searchPlaceholder')}
                            aria-label={t('searchPlaceholder')}
                        />
                        <div className="border rounded-lg divide-y max-h-80 overflow-y-auto">
                            {visibleTerms.map(term => (
                                <div key={term} className="flex items-center justify-between px-3 py-1.5 text-sm">
                                    <span className="break-all">{term}</span>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-7 w-7 shrink-0"
                                        onClick={() => setDraftTerms(draftTerms.filter(existing => existing !== term))}
                                        aria-label={t('removeTerm', { term })}
                                    >
                                        <X className="h-3.5 w-3.5" />
                                    </Button>
                                </div>
                            ))}
                            {filteredTerms.length === 0 && (
                                <div className="px-3 py-4 text-sm text-center text-muted-foreground">
                                    {search ? t('noMatches') : t('noTerms')}
                                </div>
                            )}
                        </div>
                        {hiddenCount > 0 && (
                            <p className="text-xs text-muted-foreground">
                                {t('moreTerms', { count: hiddenCount })}
                            </p>
                        )}

                        <div className="flex gap-2">
                            <Button onClick={save} disabled={busy || !isDirty || !draftName.trim()}>
                                {busy ? t('common:saving') : t('common:save')}
                            </Button>
                            {isDirty && (
                                <Button
                                    variant="outline"
                                    onClick={() => {
                                        setDraftName(detail.name);
                                        setDraftTerms(detail.terms);
                                    }}
                                >
                                    {t('common:cancel')}
                                </Button>
                            )}
                        </div>

                        <div className="border rounded-lg p-4 space-y-3">
                            <div className="font-medium">{t('uploadTitle')}</div>
                            <p className="text-sm text-muted-foreground whitespace-pre-line">{t('uploadFormat')}</p>
                            <div className="flex flex-wrap items-center gap-2">
                                <Button
                                    type="button"
                                    size="sm"
                                    variant={uploadMode === 'append' ? 'default' : 'outline'}
                                    onClick={() => setUploadMode('append')}
                                >
                                    {t('modeAppend')}
                                </Button>
                                <Button
                                    type="button"
                                    size="sm"
                                    variant={uploadMode === 'replace' ? 'default' : 'outline'}
                                    onClick={() => setUploadMode('replace')}
                                >
                                    {t('modeReplace')}
                                </Button>
                                <input
                                    ref={fileInput}
                                    type="file"
                                    accept=".txt,.csv,text/plain,text/csv"
                                    className="hidden"
                                    data-testid="dictionary-upload"
                                    onChange={e => {
                                        const file = e.target.files?.[0];
                                        if (file) upload(file);
                                    }}
                                />
                                <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    disabled={busy}
                                    onClick={() => fileInput.current?.click()}
                                >
                                    <Upload className="h-4 w-4 mr-2" />
                                    {t('chooseFile')}
                                </Button>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
};

export default DictionarySettings;
