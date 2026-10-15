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

const NUM_ORB_POINTS = 32;

/** Large, centered, sharply-spiking orb shown in place of the transcript when live
 *  transcription is off. */
export const VoiceVisualizer = ({ analyser, className }: VisualizerProps) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useCanvasLoop(canvasRef, analyser, (ctx, dataArray, bufferLength, displayWidth, displayHeight) => {
        const cx = displayWidth / 2;
        const cy = displayHeight / 2;
        const baseRadius = Math.min(displayWidth, displayHeight) * 0.25;
        const maxSpike = baseRadius * 0.9;

        const relevantBufferLength = Math.floor(bufferLength / 2);
        const bandSize = Math.max(1, Math.floor(relevantBufferLength / NUM_ORB_POINTS));
        const t = performance.now() / 1000;

        const points: { x: number; y: number }[] = [];
        for (let i = 0; i < NUM_ORB_POINTS; i++) {
            let sum = 0;
            const start = i * bandSize;
            const end = Math.min(start + bandSize, relevantBufferLength);
            for (let j = start; j < end; j++) {
                sum += dataArray[j];
            }
            const avg = sum / Math.max(1, end - start) / 255;
            // Square the response so quiet bands stay close to baseRadius and only
            // real transients shoot outward — sharp spikes instead of a gentle wobble.
            const spike = avg * avg * maxSpike;

            // Tiny idle jitter so the outline isn't a perfectly static circle in silence.
            const idleJitter = Math.sin(t * 1.2 + i) * 0.01 * baseRadius;

            const radius = baseRadius + spike + idleJitter;
            const angle = (i / NUM_ORB_POINTS) * Math.PI * 2;
            points.push({
                x: cx + Math.cos(angle) * radius,
                y: cy + Math.sin(angle) * radius,
            });
        }

        // Straight lines between points (no curve smoothing) so peaks stay sharp and pointed.
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.closePath();

        ctx.save();
        ctx.shadowColor = "rgba(239, 68, 68, 0.6)";
        ctx.shadowBlur = 30;
        ctx.strokeStyle = "rgba(239, 68, 68, 0.9)";
        ctx.lineWidth = Math.max(2, baseRadius * 0.06);
        ctx.stroke();
        ctx.restore();
    });

    return (
        <div className={cn("h-full w-full flex items-center justify-center", className)}>
            <canvas ref={canvasRef} className="h-full w-full" />
        </div>
    );
};
