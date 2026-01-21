import { cn } from "@/lib/utils";

interface LogoProps {
    className?: string;
}

export const Logo = ({ className }: LogoProps) => {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 210 100"
            fill="none"
            className={cn("w-full h-auto", className)}
        >
            <title>aidox</title>
            {/* "ai" */}
            <text x="20" y="70" fontFamily="Arial, sans-serif" fontWeight="bold" fontSize="60" className="fill-slate-900 dark:fill-slate-50" letterSpacing="-2">ai</text>

            {/* "ox" - Cyan */}
            <text x="130" y="70" fontFamily="Arial, sans-serif" fontWeight="bold" fontSize="60" className="fill-[#06b6d4]" letterSpacing="-2">ox</text>

            {/* "d" - Matches "ai" color */}
            <text x="80" y="70" fontFamily="Arial, sans-serif" fontWeight="bold" fontSize="60" className="fill-slate-900 dark:fill-slate-50" letterSpacing="-2">d</text>

            {/* Heartbeat Line - Cyan */}
            <path
                d="M 60 55 L 85 55 L 90 35 L 100 80 L 110 45 L 115 55 L 190 55"
                className="stroke-[#06b6d4]"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray="300"
                strokeDashoffset="0"
            >
                <animate attributeName="stroke-dashoffset" from="300" to="0" dur="2s" fill="freeze" />
            </path>
        </svg>
    );
};
