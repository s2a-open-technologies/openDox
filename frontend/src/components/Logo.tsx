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

import { cn } from "@/lib/utils";

interface LogoProps {
    className?: string;
}

export const Logo = ({ className }: LogoProps) => {
    return (
        <svg
            viewBox="-15 10 220 45"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className={cn("w-full h-auto", className)}
        >
            <text x="10" y="45" fontFamily="Arial, sans-serif" fontWeight="800" fontSize="38" letterSpacing="-1.5">
                <tspan fill="#1A2B6D" className="dark:fill-white">open</tspan>
                <tspan fill="#00CED1">Dox</tspan>
            </text>

            <path
                d="M5 35H120L125 20L135 55L145 10L155 50L165 25L175 35H220"
                stroke="black" className="dark:stroke-white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ mixBlendMode: 'overlay', opacity: 0.9 }}
                strokeDasharray="290"
                strokeDashoffset="0"
            >
                <animate attributeName="stroke-dashoffset" from="300" to="0" dur="1.2s" fill="freeze" />
            </path>
        </svg>
    );
};
