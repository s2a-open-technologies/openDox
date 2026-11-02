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

import * as React from "react"
import { useTranslation } from "react-i18next"
import { Upload } from "lucide-react"
import { toast } from "sonner"

import { cn } from "@/lib/utils"

interface FileDropzoneProps {
  /** Same syntax as the input's accept attribute, also checked on drop. */
  accept?: string
  onFile: (file: File) => void
  disabled?: boolean
  label: string
  /** Shown below the label; defaults to "drag here or click". */
  hint?: string
  /** Currently selected file, shown instead of the hint. */
  file?: File | null
  /** Single-line variant for tight spots (e.g. next to a button). */
  compact?: boolean
  className?: string
  /** Forwarded to the hidden input, for tests. */
  inputTestId?: string
}

/** Whether a dropped file matches an accept string (".pem", "audio/*", "text/csv"). */
export function matchesAccept(file: File, accept?: string): boolean {
  if (!accept) return true
  const name = file.name.toLowerCase()
  const type = file.type.toLowerCase()
  return accept.split(",").some((raw) => {
    const rule = raw.trim().toLowerCase()
    if (!rule) return false
    if (rule.startsWith(".")) return name.endsWith(rule)
    if (rule.endsWith("/*")) return type.startsWith(rule.slice(0, -1))
    return type === rule
  })
}

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Click-or-drop file picker with a visible hover and drag state. */
const FileDropzone = ({
  accept,
  onFile,
  disabled = false,
  label,
  hint,
  file,
  compact = false,
  className,
  inputTestId,
}: FileDropzoneProps) => {
  const { t } = useTranslation("common")
  const inputRef = React.useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = React.useState(false)

  const take = (picked: File | undefined) => {
    if (!picked) return
    if (!matchesAccept(picked, accept)) {
      toast.error(t("dropzone.notAccepted", { name: picked.name }))
      return
    }
    onFile(picked)
  }

  const open = () => {
    if (!disabled) inputRef.current?.click()
  }

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label={label}
      onClick={open}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          open()
        }
      }}
      onDragOver={(e) => {
        if (disabled) return
        e.preventDefault()
        setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setIsDragging(false)
        if (!disabled) take(e.dataTransfer.files?.[0])
      }}
      className={cn(
        "flex items-center gap-3 rounded-md border-2 border-dashed border-input text-sm transition-colors",
        "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        compact ? "px-3 py-2" : "flex-col justify-center px-4 py-6 text-center",
        disabled
          ? "cursor-not-allowed opacity-50"
          : "cursor-pointer hover:border-primary hover:bg-primary/5",
        isDragging && "border-primary bg-primary/10",
        className
      )}
    >
      <Upload className={cn("shrink-0 text-primary", compact ? "h-4 w-4" : "h-6 w-6")} />
      <div className={cn("min-w-0", compact && "flex-1")}>
        <p className="font-medium">{label}</p>
        <p className="truncate text-xs text-muted-foreground">
          {file
            ? t("dropzone.selected", { name: file.name, size: formatSize(file.size) })
            : hint ?? t("dropzone.hint")}
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        disabled={disabled}
        className="hidden"
        data-testid={inputTestId}
        onClick={(e) => e.stopPropagation()}
        onChange={(e) => {
          take(e.target.files?.[0])
          // Allow picking the same file again.
          e.target.value = ""
        }}
      />
    </div>
  )
}

export { FileDropzone }
