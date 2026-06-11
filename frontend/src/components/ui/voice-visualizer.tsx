/*
  openDox - Medical transcription platform
  Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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

interface VoiceVisualizerProps {
    analyser: AnalyserNode | null;
    className?: string;
}

export const VoiceVisualizer = ({ analyser, className }: VoiceVisualizerProps) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

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

        const draw = () => {
            animationId = requestAnimationFrame(draw);

            analyser.getByteFrequencyData(dataArray);

            const displayWidth = canvas.width / window.devicePixelRatio;
            const displayHeight = canvas.height / window.devicePixelRatio;

            ctx.clearRect(0, 0, displayWidth, displayHeight);

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
        };

        draw();

        return () => {
            cancelAnimationFrame(animationId);
            window.removeEventListener("resize", resizeCanvas);
        };
    }, [analyser]);

    return (
        <div className={cn("w-full h-16 flex items-center justify-center", className)}>
             <canvas
                ref={canvasRef}
                className="h-full w-full max-w-md opacity-80"
            />
        </div>
    );
};
