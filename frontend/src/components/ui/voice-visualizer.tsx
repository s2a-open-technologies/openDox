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

        // Configuration
        // We only want to visualize the lower frequencies where speech usually is
        // so we skip the higher part of the buffer
        const relevantBufferLength = Math.floor(bufferLength / 2);
        const barWidth = 4;
        const gap = 2;
        const totalBars = Math.floor(canvas.width / (barWidth + gap));

        const draw = () => {
            animationId = requestAnimationFrame(draw);

            analyser.getByteFrequencyData(dataArray);

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Gradient for bars
            const gradient = ctx.createLinearGradient(0, canvas.height, 0, 0);
            gradient.addColorStop(0, "rgba(239, 68, 68, 0.5)"); // Red-500
            gradient.addColorStop(1, "rgba(239, 68, 68, 1)");   // Red-500

            ctx.fillStyle = gradient;

            // We map the relevant buffer length to totalBars
            const step = Math.floor(relevantBufferLength / totalBars);

            for (let i = 0; i < totalBars; i++) {
                // Average the value for this bar's range
                let value = 0;
                const start = i * step;
                const end = start + step;
                for (let j = start; j < end; j++) {
                    value += dataArray[j];
                }
                value = value / step;

                // Enhance changes for visual effect
                // Scale opacity or height
                const height = (value / 255) * canvas.height;

                // Draw rounded bar
                const x = i * (barWidth + gap);
                const y = canvas.height - height;

                ctx.beginPath();
                ctx.roundRect(x, y, barWidth, height, 4);
                ctx.fill();
            }
        };

        draw();

        return () => {
            cancelAnimationFrame(animationId);
        };
    }, [analyser]);

    return (
        <div className={cn("w-full h-16 flex items-center justify-center", className)}>
            <canvas
                ref={canvasRef}
                width={300}
                height={64}
                className="w-full h-full max-w-xs opacity-80"
            />
        </div>
    );
};
