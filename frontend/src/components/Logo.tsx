import { cn } from "@/lib/utils";

interface LogoProps {
    className?: string;
}

export const Logo = ({ className }: LogoProps) => {
    return (
        <svg
            width="340"
            height="60"
            viewBox="0 0 340 60"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className={cn("w-full h-auto", className)}
        >
            <text x="10" y="45" fontFamily="Arial, sans-serif" fontWeight="800" fontSize="38" letterSpacing="-1.5">
                <tspan fill="#1A2B6D" className="dark:fill-white">open</tspan>
                <tspan fill="#1A2B6D" className="dark:fill-white">D</tspan>
                <tspan fill="#00CED1">ox</tspan>
            </text>

            <path
                d="M0 35H120L125 20L135 55L145 10L155 50L165 25L175 35H220"
                stroke="black" className="dark:stroke-white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ mixBlendMode: 'overlay', opacity: 0.9 }}
                strokeDasharray="300"
                strokeDashoffset="0"
            >
                <animate attributeName="stroke-dashoffset" from="300" to="0" dur="1.2s" fill="freeze" />
            </path>
        </svg>
    );
};
