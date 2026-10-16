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

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

interface VisualizerProps {
    analyser: AnalyserNode | null;
    className?: string;
}

/** Sets up canvas sizing + a requestAnimationFrame loop, delegating the actual per-frame
 *  drawing to `draw`. Shared by both the live bar spectrum and the orb visual. */
function useCanvasLoop(
    canvasRef: React.RefObject<HTMLCanvasElement>,
    analyser: AnalyserNode | null,
    draw: (ctx: CanvasRenderingContext2D, dataArray: Uint8Array, bufferLength: number, displayWidth: number, displayHeight: number) => void
) {
    useEffect(() => {
        if (!analyser || !canvasRef.current) return;

        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        let animationId: number;

        const resizeCanvas = () => {
            const rect = canvas.getBoundingClientRect();
            canvas.width = rect.width * window.devicePixelRatio;
            canvas.height = rect.height * window.devicePixelRatio;
            ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        };

        resizeCanvas();
        window.addEventListener("resize", resizeCanvas);

        const loop = () => {
            animationId = requestAnimationFrame(loop);

            analyser.getByteFrequencyData(dataArray);

            const displayWidth = canvas.width / window.devicePixelRatio;
            const displayHeight = canvas.height / window.devicePixelRatio;

            ctx.clearRect(0, 0, displayWidth, displayHeight);
            draw(ctx, dataArray, bufferLength, displayWidth, displayHeight);
        };

        loop();

        return () => {
            cancelAnimationFrame(animationId);
            window.removeEventListener("resize", resizeCanvas);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [analyser, draw]);
}

/** Small red frequency-bar spectrum, shown alongside the live transcript. */
export const BarVisualizer = ({ analyser, className }: VisualizerProps) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useCanvasLoop(canvasRef, analyser, (ctx, dataArray, bufferLength, displayWidth, displayHeight) => {
        const relevantBufferLength = Math.floor(bufferLength / 2);
        const barWidth = 4;
        const gap = 2;
        const totalBars = Math.floor(displayWidth / (barWidth + gap));

        const gradient = ctx.createLinearGradient(0, displayHeight, 0, 0);
        gradient.addColorStop(0, "rgba(239, 68, 68, 0.5)");
        gradient.addColorStop(1, "rgba(239, 68, 68, 1)");

        ctx.fillStyle = gradient;

        const step = Math.max(1, Math.floor(relevantBufferLength / totalBars));

        for (let i = 0; i < totalBars; i++) {
            let value = 0;
            const start = i * step;
            const end = Math.min(start + step, relevantBufferLength);
            for (let j = start; j < end; j++) {
                value += dataArray[j];
            }
            value = value / Math.max(1, end - start);

            const height = (value / 255) * displayHeight;

            const x = i * (barWidth + gap);
            const y = displayHeight - height;

            ctx.beginPath();
            ctx.roundRect(x, y, barWidth, height, 2);
            ctx.fill();
        }
    });

    return (
        <div className={cn("w-full h-16 flex items-center justify-center", className)}>
            <canvas
                ref={canvasRef}
                className="h-full w-full max-w-md opacity-80"
            />
        </div>
    );
};

const NUM_ORB_POINTS = 48;
// Cyan of "Dox" in the openDox logo (Logo.tsx, #00CED1).
const ORB_RGB = "0, 206, 209";

/** Closed, smooth blob through `pts` (quadratic curves via the midpoints). */
function blobPath(ctx: CanvasRenderingContext2D, pts: { x: number; y: number }[]) {
    const n = pts.length;
    ctx.beginPath();
    ctx.moveTo((pts[n - 1].x + pts[0].x) / 2, (pts[n - 1].y + pts[0].y) / 2);
    for (let i = 0; i < n; i++) {
        const p = pts[i];
        const q = pts[(i + 1) % n];
        ctx.quadraticCurveTo(p.x, p.y, (p.x + q.x) / 2, (p.y + q.y) / 2);
    }
    ctx.closePath();
}

/** Large, centered orb in the openDox "Dox" cyan, shown in place of the transcript when
 *  live transcription is off. Reacts to the spectrum with a soft, glowing blob. */
export const VoiceVisualizer = ({ analyser, className }: VisualizerProps) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const smoothed = useRef<number[]>(new Array(NUM_ORB_POINTS).fill(0));

    useCanvasLoop(canvasRef, analyser, (ctx, dataArray, bufferLength, displayWidth, displayHeight) => {
        const cx = displayWidth / 2;
        const cy = displayHeight / 2;
        const baseRadius = Math.min(displayWidth, displayHeight) * 0.22;
        const maxSpike = baseRadius * 0.7;
        const t = performance.now() / 1000;

        const relevantBufferLength = Math.floor(bufferLength / 2);
        const bandSize = Math.max(1, Math.floor(relevantBufferLength / NUM_ORB_POINTS));

        // Mirror the spectrum left/right so the orb is symmetric, and ease each point
        // towards its target so it breathes instead of flickering.
        const half = NUM_ORB_POINTS / 2;
        let level = 0;
        for (let i = 0; i < NUM_ORB_POINTS; i++) {
            const band = i < half ? i : NUM_ORB_POINTS - 1 - i;
            let sum = 0;
            const start = band * bandSize;
            const end = Math.min(start + bandSize, relevantBufferLength);
            for (let j = start; j < end; j++) sum += dataArray[j];
            const avg = sum / Math.max(1, end - start) / 255;
            smoothed.current[i] += (avg - smoothed.current[i]) * 0.25;
            level += smoothed.current[i];
        }
        level /= NUM_ORB_POINTS;

        const buildPoints = (scale: number, phase: number) => {
            const pts: { x: number; y: number }[] = [];
            for (let i = 0; i < NUM_ORB_POINTS; i++) {
                const angle = (i / NUM_ORB_POINTS) * Math.PI * 2 - Math.PI / 2;
                const breathe = Math.sin(t * 1.3 + i * 0.5 + phase) * 0.018 * baseRadius;
                const r = (baseRadius + smoothed.current[i] ** 1.5 * maxSpike + breathe) * scale;
                pts.push({ x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r });
            }
            return pts;
        };

        const pulse = 1 + level * 0.12;

        // Soft halo behind the orb.
        const halo = ctx.createRadialGradient(cx, cy, baseRadius * 0.4, cx, cy, baseRadius * (2.2 + level));
        halo.addColorStop(0, `rgba(${ORB_RGB}, ${0.28 + level * 0.3})`);
        halo.addColorStop(1, `rgba(${ORB_RGB}, 0)`);
        ctx.fillStyle = halo;
        ctx.fillRect(0, 0, displayWidth, displayHeight);

        // Two fainter echo layers, slightly larger and phase-shifted.
        [1.18, 1.09].forEach((scale, k) => {
            blobPath(ctx, buildPoints(scale * pulse, (k + 1) * 1.7));
            ctx.strokeStyle = `rgba(${ORB_RGB}, ${0.16 + k * 0.1})`;
            ctx.lineWidth = 1.5;
            ctx.stroke();
        });

        // Main body: radial gradient from a bright core to the logo cyan.
        blobPath(ctx, buildPoints(pulse, 0));
        const body = ctx.createRadialGradient(
            cx - baseRadius * 0.3, cy - baseRadius * 0.35, baseRadius * 0.1,
            cx, cy, baseRadius * 1.4,
        );
        body.addColorStop(0, "rgba(190, 255, 255, 0.95)");
        body.addColorStop(0.45, `rgba(${ORB_RGB}, 0.85)`);
        body.addColorStop(1, `rgba(0, 120, 140, 0.55)`);

        ctx.save();
        ctx.shadowColor = `rgba(${ORB_RGB}, 0.7)`;
        ctx.shadowBlur = 35 + level * 40;
        ctx.fillStyle = body;
        ctx.fill();
        ctx.restore();

        ctx.strokeStyle = "rgba(220, 255, 255, 0.7)";
        ctx.lineWidth = Math.max(1.5, baseRadius * 0.025);
        ctx.stroke();
    });

    return (
        <div className={cn("h-full w-full flex items-center justify-center", className)}>
            <canvas ref={canvasRef} className="h-full w-full" />
        </div>
    );
};
