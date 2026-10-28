/*
  openDox - Medical transcription platform
  Copyright (C) 2026  S2A Open Technologies gGmbH
  SPDX-FileCopyrightText: 2026 S2A Open Technologies gGmbH
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

import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Download, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/contexts/AuthContext';

interface AuditEvent {
  id: number;
  timestamp: string;
  actor_name: string | null;
  actor_role: string | null;
  action: string;
  outcome: 'success' | 'failure' | 'denied';
  target_type: string | null;
  target_id: string | null;
  ip: string | null;
  details: Record<string, unknown> | null;
}

interface Filters {
  since: string;
  until: string;
  actor: string;
  action: string;
  outcome: string;
}

const PAGE_SIZE = 50;
const ACTION_GROUPS = ['auth', 'access', 'user', 'settings', 'category', 'dictionary', 'language', 'backup', 'task', 'audit'];
const OUTCOMES = ['success', 'failure', 'denied'];
const EMPTY_FILTERS: Filters = { since: '', until: '', actor: '', action: '', outcome: '' };
const SELECT_CLASS =
  'flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring';

/** Query string for the list/export endpoints; dates are whole days in local time. */
function filterParams(filters: Filters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.since) params.set('since', new Date(`${filters.since}T00:00:00`).toISOString());
  if (filters.until) params.set('until', new Date(`${filters.until}T23:59:59.999`).toISOString());
  if (filters.actor.trim()) params.set('actor', filters.actor.trim());
  if (filters.action) params.set('action', `${filters.action}.`);
  if (filters.outcome) params.set('outcome', filters.outcome);
  return params;
}

const OUTCOME_VARIANT: Record<AuditEvent['outcome'], 'secondary' | 'destructive' | 'outline'> = {
  success: 'secondary',
  failure: 'outline',
  denied: 'destructive',
};

export function AuditLog() {
  const { t, i18n } = useTranslation(['audit', 'common']);
  const { authFetch } = useAuth();
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS);
  const [offset, setOffset] = useState(0);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = filterParams(applied);
      params.set('offset', String(offset));
      params.set('limit', String(PAGE_SIZE));
      const res = await authFetch(`/api/v1/settings/audit/?${params}`);
      if (!res.ok) throw new Error();
      const page = await res.json();
      setEvents(page.items);
      setTotal(page.total);
    } catch {
      toast.error(t('loadFailed'));
    } finally {
      setLoading(false);
    }
    // authFetch is recreated on every AuthProvider render; depending on it
    // would reload the page without any filter change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applied, offset]);

  useEffect(() => {
    load();
  }, [load]);

  const apply = () => {
    setOffset(0);
    setApplied(filters);
  };

  const reset = () => {
    setFilters(EMPTY_FILTERS);
    setOffset(0);
    setApplied(EMPTY_FILTERS);
  };

  const exportCsv = async () => {
    setExporting(true);
    try {
      const res = await authFetch(`/api/v1/settings/audit/export/?${filterParams(applied)}`);
      if (!res.ok) throw new Error();
      const blob = await res.blob();
      const match = (res.headers.get('content-disposition') || '').match(/filename="?([^"]+)"?/);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = match ? match[1] : 'opendox-audit.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      toast.error(t('exportFailed'));
    } finally {
      setExporting(false);
    }
  };

  const actionLabel = (action: string) =>
    t(`actions.${action.replace(/\./g, '_')}`, { defaultValue: action });

  const describe = (event: AuditEvent): string => {
    const d = event.details ?? {};
    const parts: string[] = [];
    if (typeof d.name === 'string') parts.push(d.name);
    if (Array.isArray(d.fields) && d.fields.length) parts.push(t('detail.fields', { fields: d.fields.join(', ') }));
    if (typeof d.reason === 'string') parts.push(t(`reasons.${d.reason}`, { defaultValue: d.reason }));
    if (typeof d.from === 'string' && typeof d.to === 'string') parts.push(`${d.from} → ${d.to}`);
    const role = d.role as { from?: string; to?: string } | undefined;
    if (role && typeof role === 'object' && role.from) parts.push(`${role.from} → ${role.to}`);
    if (typeof d.method === 'string' && typeof d.path === 'string') parts.push(`${d.method} ${d.path}`);
    if (Array.isArray(d.sections)) parts.push(d.sections.join(', '));
    if (typeof d.filename === 'string') parts.push(d.filename);
    return parts.join(' · ');
  };

  const setFilter = (key: keyof Filters) => (value: string) => setFilters((prev) => ({ ...prev, [key]: value }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('title')}</CardTitle>
        <CardDescription>{t('description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="space-y-1">
            <Label htmlFor="audit-since">{t('filter.since')}</Label>
            <Input id="audit-since" type="date" value={filters.since} onChange={(e) => setFilter('since')(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="audit-until">{t('filter.until')}</Label>
            <Input id="audit-until" type="date" value={filters.until} onChange={(e) => setFilter('until')(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="audit-actor">{t('filter.actor')}</Label>
            <Input id="audit-actor" value={filters.actor} onChange={(e) => setFilter('actor')(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="audit-action">{t('filter.action')}</Label>
            <select id="audit-action" className={SELECT_CLASS} value={filters.action} onChange={(e) => setFilter('action')(e.target.value)}>
              <option value="">{t('filter.all')}</option>
              {ACTION_GROUPS.map((group) => (
                <option key={group} value={group}>{t(`groups.${group}`)}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="audit-outcome">{t('filter.outcome')}</Label>
            <select id="audit-outcome" className={SELECT_CLASS} value={filters.outcome} onChange={(e) => setFilter('outcome')(e.target.value)}>
              <option value="">{t('filter.all')}</option>
              {OUTCOMES.map((outcome) => (
                <option key={outcome} value={outcome}>{t(`outcomes.${outcome}`)}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={apply}>{t('filter.apply')}</Button>
          <Button size="sm" variant="outline" onClick={reset}>{t('filter.reset')}</Button>
          <Button size="sm" variant="outline" onClick={load} disabled={loading} aria-label={t('refresh')}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button size="sm" variant="outline" className="ml-auto flex items-center gap-2" onClick={exportCsv} disabled={exporting}>
            <Download className="h-4 w-4" />
            {t('export')}
          </Button>
        </div>

        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left">
              <tr>
                <th className="px-3 py-2 font-medium">{t('columns.time')}</th>
                <th className="px-3 py-2 font-medium">{t('columns.actor')}</th>
                <th className="px-3 py-2 font-medium">{t('columns.action')}</th>
                <th className="px-3 py-2 font-medium">{t('columns.outcome')}</th>
                <th className="px-3 py-2 font-medium">{t('columns.details')}</th>
                <th className="px-3 py-2 font-medium">{t('columns.ip')}</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id} className="border-t align-top">
                  <td className="whitespace-nowrap px-3 py-2">{new Date(event.timestamp).toLocaleString(i18n.language)}</td>
                  <td className="px-3 py-2">
                    <div>{event.actor_name ?? t('system')}</div>
                    {event.actor_role && <div className="text-xs text-muted-foreground">{event.actor_role}</div>}
                  </td>
                  <td className="px-3 py-2">{actionLabel(event.action)}</td>
                  <td className="px-3 py-2">
                    <Badge variant={OUTCOME_VARIANT[event.outcome] ?? 'outline'}>{t(`outcomes.${event.outcome}`, { defaultValue: event.outcome })}</Badge>
                  </td>
                  <td className="px-3 py-2 break-words text-muted-foreground">{describe(event)}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-muted-foreground">{event.ip ?? ''}</td>
                </tr>
              ))}
              {events.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-muted-foreground">{t('empty')}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{t('pagination.range', { from: total ? offset + 1 : 0, to: Math.min(offset + PAGE_SIZE, total), total })}</span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
              {t('pagination.previous')}
            </Button>
            <Button size="sm" variant="outline" disabled={offset + PAGE_SIZE >= total || loading} onClick={() => setOffset(offset + PAGE_SIZE)}>
              {t('pagination.next')}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
