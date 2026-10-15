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

import { apiErrorMessage } from '@/lib/apiError';
import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { RotateCcw } from 'lucide-react';
import { toast } from 'sonner';

interface FailedTask {
  task_id: number;
  record_id: number;
  title: string;
  error: string | null;
  updated_at: string;
}

export function FailedTranscriptions({ readOnly = false }: { readOnly?: boolean }) {
  const { t, i18n } = useTranslation(['failed', 'common']);
  const { authFetch } = useAuth();
  const [tasks, setTasks] = useState<FailedTask[]>([]);
  const [retryingId, setRetryingId] = useState<number | null>(null);

  const fetchFailedTasks = async () => {
    try {
      const res = await authFetch('/api/v1/records/tasks/failed');
      if (res.ok) {
        setTasks(await res.json());
      }
    } catch (error) {
      console.error('Failed to fetch failed transcriptions:', error);
    }
  };

  useEffect(() => {
    fetchFailedTasks();
  }, []);

  const retry = async (taskId: number) => {
    setRetryingId(taskId);
    try {
      const res = await authFetch(`/api/v1/records/tasks/${taskId}/retry`, { method: 'POST' });
      if (res.ok) {
        toast.success(t('retrying'));
        setTasks((prev) => prev.filter((task) => task.task_id !== taskId));
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(apiErrorMessage(err, t('retryFailed')));
      }
    } catch (error) {
      console.error('Failed to retry task:', error);
      toast.error(t('common:connectionError'));
    } finally {
      setRetryingId(null);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('title')}</CardTitle>
        <CardDescription>
          {t('description')}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {tasks.map((task) => (
            <div
              key={task.task_id}
              className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent/50 transition-colors"
            >
              <div className="space-y-1">
                <div className="font-medium">{task.title || t('recording', { id: task.record_id })}</div>
                <div className="text-sm text-muted-foreground">
                  {task.error || t('unknownError')}
                </div>
                <div className="text-xs text-muted-foreground/70">
                  {new Date(task.updated_at).toLocaleString(i18n.language)}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="flex items-center gap-2"
                disabled={retryingId === task.task_id || readOnly}
                onClick={() => retry(task.task_id)}
              >
                <RotateCcw className="h-4 w-4" />
                {t('retry')}
              </Button>
            </div>
          ))}
          {tasks.length === 0 && (
            <div className="text-center text-muted-foreground py-8">
              {t('empty')}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
