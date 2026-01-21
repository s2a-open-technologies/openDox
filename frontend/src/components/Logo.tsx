import { cn } from "@/lib/utils";

interface LogoProps {
    className?: string;
}

export const Logo = ({ className }: LogoProps) => {
    return (
        <svg
            width="210"
            height="60"
            viewBox="0 0 210 60"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className={cn("w-full h-auto", className)}
        >
            <text x="10" y="45" fontFamily="Arial, sans-serif" fontWeight="800" fontSize="38" letterSpacing="-1.5">
                <tspan fill="#1A2B6D" className="dark:fill-white">ai</tspan>
                <tspan fill="#00CED1">dox</tspan>
            </text>

            <path
                d="M0 35H40L45 25L55 55L65 15L75 45L85 30L95 40H110"
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
