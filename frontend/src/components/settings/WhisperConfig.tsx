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

import { apiErrorMessage } from '@/lib/apiError';
import { useTranslation } from 'react-i18next';
import { useState, useEffect, useCallback } from 'react';
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
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

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
    left_context_s: number;
    // Anti-hallucination / faster-whisper tuning
    temperature: number;
    vad_filter: boolean;
    vad_min_silence_ms: number;
    condition_on_previous_text: boolean;
    no_speech_threshold: number;
    compression_ratio_threshold: number;
    log_prob_threshold: number;
    hallucination_silence_threshold: number | null;
    live_beam_size: number;
    final_beam_size: number;
    // Phonetic/fuzzy post-correction of the final transcript
    term_correction_enabled: boolean;
    term_correction_threshold: number;
}

type WhisperSettingsResponse = Partial<WhisperSettings>;

type TestResult = { ok: boolean; message: string } | null;

const WhisperConfig = ({ readOnly = false }: { readOnly?: boolean }) => {
    const { t } = useTranslation(['whisper', 'common']);
    const { authFetch } = useAuth();
    const [liveTest, setLiveTest] = useState<{ status: 'idle' | 'testing' | 'done'; result: TestResult }>({
        status: 'idle',
        result: null,
    });
    const [finalTest, setFinalTest] = useState<{ status: 'idle' | 'testing' | 'done'; result: TestResult }>({
        status: 'idle',
        result: null,
    });
    const [config, setConfig] = useState<WhisperSettings>({
        live_backend: 'api',
        live_api_endpoint: '',
        live_api_key: '',
        live_api_model: '',
        final_backend: 'api',
        final_api_endpoint: '',
        final_api_key: '',
        final_api_model: '',
        language: 'de',
        chunk_length_s: 3,
        overlap_s: 0,
        left_context_s: 1,
        temperature: 0.0,
        vad_filter: true,
        vad_min_silence_ms: 500,
        condition_on_previous_text: false,
        no_speech_threshold: 0.6,
        compression_ratio_threshold: 2.4,
        log_prob_threshold: -1.0,
        hallucination_silence_threshold: null,
        live_beam_size: 1,
        final_beam_size: 5,
        term_correction_enabled: false,
        term_correction_threshold: 85.0,
    });

    useEffect(() => {
        authFetch('/api/v1/settings/whisper-settings/')
            .then(res => res.json())
            .then((data: WhisperSettingsResponse) => {
                setConfig({
                    live_backend: data.live_backend || 'api',
                    live_api_endpoint: data.live_api_endpoint || '',
                    live_api_key: data.live_api_key || '',
                    live_api_model: data.live_api_model || '',
                    final_backend: data.final_backend || 'api',
                    final_api_endpoint: data.final_api_endpoint || '',
                    final_api_key: data.final_api_key || '',
                    final_api_model: data.final_api_model || '',
                    language: data.language || 'de',
                    chunk_length_s: data.chunk_length_s ?? 3,
                    overlap_s: data.overlap_s ?? 0,
                    left_context_s: data.left_context_s ?? 1,
                    temperature: data.temperature ?? 0.0,
                    vad_filter: data.vad_filter ?? true,
                    vad_min_silence_ms: data.vad_min_silence_ms ?? 500,
                    condition_on_previous_text: data.condition_on_previous_text ?? false,
                    no_speech_threshold: data.no_speech_threshold ?? 0.6,
                    compression_ratio_threshold: data.compression_ratio_threshold ?? 2.4,
                    log_prob_threshold: data.log_prob_threshold ?? -1.0,
                    hallucination_silence_threshold: data.hallucination_silence_threshold ?? null,
                    live_beam_size: data.live_beam_size ?? 1,
                    final_beam_size: data.final_beam_size ?? 5,
                    term_correction_enabled: data.term_correction_enabled ?? false,
                    term_correction_threshold: data.term_correction_threshold ?? 85.0,
                });
            })
            .catch(console.error);
    }, []);

    const updateField = (key: keyof WhisperSettings, value: WhisperSettings[keyof WhisperSettings]) => {
        setConfig(prev => ({ ...prev, [key]: value }));
    };

    const saveConfig = async () => {
        try {
            const res = await authFetch('/api/v1/settings/whisper-settings/', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            if (res.ok) {
                toast.success(t('saved'));
            } else {
                toast.error(t('common:saveFailed'));
            }
        } catch {
            toast.error(t('common:connectionError'));
        }
    };

    const testAsr = async (which: 'live' | 'final') => {
        const setter = which === 'live' ? setLiveTest : setFinalTest;
        setter({ status: 'testing', result: null });
        try {
            const res = await authFetch(`/api/v1/settings/asr-test/?backend=${which}`);
            const data = await res.json();
            if (data.ok) {
                setter({ status: 'done', result: { ok: true, message: data.model ? t('test.reachableModel', { model: data.model }) : t('test.reachable') } });
            } else {
                setter({ status: 'done', result: { ok: false, message: apiErrorMessage(data, t('test.unreachable')) } });
            }
        } catch {
            setter({ status: 'done', result: { ok: false, message: t('test.requestFailed') } });
        }
    };

    return (
        <div className="space-y-4">
            <h3 className="text-lg font-medium">{t('title')}</h3>
            
            <Tabs defaultValue="general" className="w-full">
                <TabsList className={`grid w-full ${config.live_backend === 'api' ? 'grid-cols-2 sm:grid-cols-4' : 'grid-cols-3'}`}>
                    <TabsTrigger value="general">{t('tabs.general')}</TabsTrigger>
                    <TabsTrigger value="live">{t('tabs.live')}</TabsTrigger>
                    <TabsTrigger value="final">{t('tabs.final')}</TabsTrigger>
                    {config.live_backend === 'api' && (
                        <TabsTrigger value="quality">{t('tabs.quality')}</TabsTrigger>
                    )}
                </TabsList>

                <TabsContent value="general">
                    <Card>
                        <CardHeader>
                            <CardTitle>{t('general.title')}</CardTitle>
                            <CardDescription>{t('general.description')}</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label>{t('general.language')}</Label>
                                <Select value={config.language} disabled={readOnly} onValueChange={(v) => updateField('language', v)}>
                                    <SelectTrigger>
                                        <SelectValue placeholder={t('choose')} />
                                    </SelectTrigger>
                                    <SelectContent>
                                    <SelectItem value="de">{t('languages.de')}</SelectItem>
                                    <SelectItem value="en">{t('languages.en')}</SelectItem>
                                    <SelectItem value="fr">{t('languages.fr')}</SelectItem>
                                    <SelectItem value="es">{t('languages.es')}</SelectItem>
                                    <SelectItem value="it">{t('languages.it')}</SelectItem>
                                    <SelectItem value="auto">{t('languages.auto')}</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="live">
                    <Card>
                        <CardHeader>
                            <CardTitle>{t('live.title')}</CardTitle>
                            <CardDescription>{t('live.description')}</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="live-enabled">{t('live.enabled')}</Label>
                                <Select value={config.live_backend} disabled={readOnly} onValueChange={(v) => updateField('live_backend', v)}>
                                    <SelectTrigger>
                                        <SelectValue placeholder={t('choose')} />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="parakeet">{t('live.backends.parakeet')}</SelectItem>
                                        <SelectItem value="api">Whisper API</SelectItem>
                                        <SelectItem value="disabled">{t('live.backends.disabled')}</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            
                            {config.live_backend !== 'disabled' && (
                                <>
                                    {config.live_backend === 'parakeet' && (
                                        <p className="text-sm text-muted-foreground">
                                            {t('live.parakeetHint')}
                                        </p>
                                    )}
                                    <div className="space-y-2">
                                        <Label>{t('apiEndpoint')}</Label>
                                        <Input
                                            placeholder={config.live_backend === 'parakeet' ? 'http://parakeet:5001/v1' : 'http://localhost:9000'}
                                            disabled={readOnly}
                                            value={config.live_api_endpoint}
                                            onChange={(e) => updateField('live_api_endpoint', e.target.value)}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>{t('apiKeyOptional')}</Label>
                                        <Input
                                            type="password"
                                            placeholder={t('bearerToken')}
                                            disabled={readOnly}
                                            value={config.live_api_key}
                                            onChange={(e) => updateField('live_api_key', e.target.value)}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>{t('model')}</Label>
                                        <Input
                                            placeholder="nemo-parakeet-tdt-0.6b-v3"
                                            disabled={readOnly}
                                            value={config.live_api_model}
                                            onChange={(e) => updateField('live_api_model', e.target.value)}
                                        />
                                    </div>
                                    {config.live_backend !== 'parakeet' && (
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <div className="space-y-2">
                                                <Label>{t('live.chunkLength')}</Label>
                                                <Input
                                                    type="number" min={1} max={10}
                                                    disabled={readOnly}
                                                    value={config.chunk_length_s}
                                                    onChange={(e) => updateField('chunk_length_s', parseInt(e.target.value) || 3)}
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>{t('live.overlap')}</Label>
                                                <Input
                                                    type="number" min={0} max={2} step={0.5}
                                                    disabled={readOnly}
                                                    value={config.overlap_s}
                                                    onChange={(e) => updateField('overlap_s', parseFloat(e.target.value) || 0)}
                                                />
                                            </div>
                                        </div>
                                    )}
                                </>
                            )}
                            <div className="flex gap-2 pt-2">
                                <Button
                                    variant="outline"
                                    onClick={() => testAsr('live')}
                                    disabled={config.live_backend === 'disabled' || liveTest.status === 'testing' || readOnly}
                                    className="gap-2"
                                >
                                    {liveTest.status === 'testing' && <Loader2 className="w-4 h-4 animate-spin" />}
                                    {t('testConnection')}
                                </Button>
                            </div>
                            {liveTest.result && (
                                <div className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${
                                    liveTest.result.ok
                                        ? 'border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-300'
                                        : 'border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300'
                                }`}>
                                    {liveTest.result.ok
                                        ? <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
                                        : <XCircle className="w-4 h-4 mt-0.5 shrink-0" />}
                                    <span>{liveTest.result.message}</span>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="final">
                    <Card>
                        <CardHeader>
                            <CardTitle>{t('final.title')}</CardTitle>
                            <CardDescription>{t('final.description')}</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label>{t('apiEndpoint')}</Label>
                                <Input 
                                    placeholder="http://localhost:9000" 
                                    disabled={readOnly}
                                    value={config.final_api_endpoint} 
                                    onChange={(e) => updateField('final_api_endpoint', e.target.value)} 
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>{t('apiKeyOptional')}</Label>
                                <Input 
                                    type="password" 
                                    placeholder={t('bearerToken')} 
                                    disabled={readOnly}
                                    value={config.final_api_key} 
                                    onChange={(e) => updateField('final_api_key', e.target.value)} 
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>{t('model')}</Label>
                                <Input 
                                    placeholder="large-v3-turbo" 
                                    disabled={readOnly}
                                    value={config.final_api_model} 
                                    onChange={(e) => updateField('final_api_model', e.target.value)}
                                />
                            </div>
                            <div className="flex items-center justify-between">
                                <Label htmlFor="term-correction-enabled">
                                    {t('final.termCorrection')}
                                </Label>
                                <Switch
                                    id="term-correction-enabled"
                                    checked={config.term_correction_enabled}
                                    disabled={readOnly}
                                    onCheckedChange={(checked) => updateField('term_correction_enabled', checked)}
                                />
                            </div>
                            {config.term_correction_enabled && (
                                <div className="space-y-2">
                                    <Label>{t('final.threshold')}</Label>
                                    <p className="text-sm text-muted-foreground">
                                        {t('final.thresholdHint')}
                                    </p>
                                    <Input
                                        type="number" min={0} max={100} step={1}
                                        disabled={readOnly}
                                        value={config.term_correction_threshold}
                                        onChange={(e) => updateField('term_correction_threshold', parseFloat(e.target.value) || 0)}
                                    />
                                </div>
                            )}
                            <div className="flex gap-2 pt-2">
                                <Button
                                    variant="outline"
                                    onClick={() => testAsr('final')}
                                    disabled={finalTest.status === 'testing' || readOnly}
                                    className="gap-2"
                                >
                                    {finalTest.status === 'testing' && <Loader2 className="w-4 h-4 animate-spin" />}
                                    {t('testConnection')}
                                </Button>
                            </div>
                            {finalTest.result && (
                                <div className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${
                                    finalTest.result.ok
                                        ? 'border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-300'
                                        : 'border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300'
                                }`}>
                                    {finalTest.result.ok
                                        ? <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
                                        : <XCircle className="w-4 h-4 mt-0.5 shrink-0" />}
                                    <span>{finalTest.result.message}</span>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="quality">
                    <Card>
                        <CardHeader>
                            <CardTitle>{t('quality.title')}</CardTitle>
                            <CardDescription>
                                {t('quality.description')}
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="vad-filter">{t('quality.vadFilter')}</Label>
                                <Switch
                                    id="vad-filter"
                                    checked={config.vad_filter}
                                    disabled={readOnly}
                                    onCheckedChange={(checked) => updateField('vad_filter', checked)}
                                />
                            </div>
                            <div className="flex items-center justify-between">
                                <Label htmlFor="cond-prev">{t('quality.condPrev')}</Label>
                                <Switch
                                    id="cond-prev"
                                    checked={config.condition_on_previous_text}
                                    disabled={readOnly}
                                    onCheckedChange={(checked) => updateField('condition_on_previous_text', checked)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>{t('quality.vadMinSilence')}</Label>
                                <Input
                                    type="number" min={0} max={5000} step={50}
                                    disabled={readOnly}
                                    value={config.vad_min_silence_ms}
                                    onChange={(e) => updateField('vad_min_silence_ms', parseInt(e.target.value) || 0)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>{t('quality.temperature')}</Label>
                                <Input
                                    type="number" min={0} max={1} step={0.1}
                                    disabled={readOnly}
                                    value={config.temperature}
                                    onChange={(e) => updateField('temperature', parseFloat(e.target.value) || 0)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>{t('quality.noSpeech')}</Label>
                                <Input
                                    type="number" min={0} max={1} step={0.05}
                                    disabled={readOnly}
                                    value={config.no_speech_threshold}
                                    onChange={(e) => updateField('no_speech_threshold', parseFloat(e.target.value) || 0)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>{t('quality.compressionRatio')}</Label>
                                <Input
                                    type="number" min={0} max={10} step={0.1}
                                    disabled={readOnly}
                                    value={config.compression_ratio_threshold}
                                    onChange={(e) => updateField('compression_ratio_threshold', parseFloat(e.target.value) || 0)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>{t('quality.logProb')}</Label>
                                <Input
                                    type="number" min={-10} max={0} step={0.1}
                                    disabled={readOnly}
                                    value={config.log_prob_threshold}
                                    onChange={(e) => updateField('log_prob_threshold', parseFloat(e.target.value) || 0)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>{t('quality.hallucinationSilence')}</Label>
                                <Input
                                    type="number" min={0} max={60} step={0.5}
                                    placeholder={t('quality.off')}
                                    disabled={readOnly}
                                    value={config.hallucination_silence_threshold ?? ''}
                                    onChange={(e) => updateField('hallucination_silence_threshold', e.target.value === '' ? null : parseFloat(e.target.value))}
                                />
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>{t('quality.beamLive')}</Label>
                                    <Input
                                        type="number" min={1} max={10}
                                        disabled={readOnly}
                                        value={config.live_beam_size}
                                        onChange={(e) => updateField('live_beam_size', parseInt(e.target.value) || 1)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>{t('quality.beamFinal')}</Label>
                                    <Input
                                        type="number" min={1} max={10}
                                        disabled={readOnly}
                                        value={config.final_beam_size}
                                        onChange={(e) => updateField('final_beam_size', parseInt(e.target.value) || 5)}
                                    />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            <Button onClick={saveConfig} disabled={readOnly} className="w-full">{t('save')}</Button>
        </div>
    );
};

export default WhisperConfig;
