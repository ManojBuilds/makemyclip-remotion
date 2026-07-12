"use client"

import { useCallback, useRef, useState } from "react"
import { toast } from "sonner"
import { useUpload } from "@/hooks/use-upload"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"

const ACCEPTED_TYPES = [
  "video/mp4",
  "video/quicktime",
  "video/webm",
  "video/x-msvideo",
  "video/x-matroska",
]

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

type UploadDropzoneProps = {
  onUploadComplete?: (projectId: string) => void
  onFileSelect?: (file: File) => void
  isFree?: boolean
}

export function UploadDropzone({
  onUploadComplete,
  onFileSelect,
  isFree = false,
}: UploadDropzoneProps) {
  const { status, progress, error, upload, reset } = useUpload()
  const [isDragging, setIsDragging] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(
    async (file: File) => {
      if (!ACCEPTED_TYPES.includes(file.type)) {
        toast.error("Please upload a video file (MP4, MOV, WebM, AVI, or MKV)")
        return
      }
      setSelectedFile(file)
      onFileSelect?.(file)
    },
    [onFileSelect]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)
      const file = e.dataTransfer.files?.[0]
      if (file) handleFile(file)
    },
    [handleFile]
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) handleFile(file)
    },
    [handleFile]
  )

  const isActive =
    status === "preparing" || status === "uploading" || status === "completing"

  if (isActive || status === "done") {
    return (
      <div className="rounded-xl border bg-card p-8">
        <div className="mx-auto max-w-md space-y-4">
          {/* File info */}
          <div className="flex items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-primary"
              >
                <path d="m16 6 4 14" />
                <path d="M12 6v14" />
                <path d="M8 8v12" />
                <path d="M4 4v16" />
              </svg>
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">
                {selectedFile?.name}
              </p>
              <p className="text-xs text-muted-foreground">
                {selectedFile ? formatFileSize(selectedFile.size) : ""}
              </p>
            </div>
          </div>

          {/* Progress */}
          <div className="space-y-2">
            <Progress value={progress} className="h-2" />
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>
                {status === "preparing" && "Preparing upload..."}
                {status === "uploading" && `Uploading... ${progress}%`}
                {status === "completing" && "Creating project..."}
                {status === "done" && "Upload complete!"}
              </span>
              {status === "uploading" && <span>{progress}%</span>}
            </div>
          </div>

          {status === "done" && (
            <p className="text-center text-sm text-green-600">
              ✓ Project created — processing will begin shortly
            </p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div
      className={cn(
        "relative cursor-pointer rounded-xl border-2 border-dashed transition-all duration-200",
        isDragging
          ? "scale-[1.01] border-primary bg-primary/5"
          : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50",
        error && "border-destructive/50 bg-destructive/5"
      )}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onClick={() => inputRef.current?.click()}
    >
      <Input
        ref={inputRef}
        type="file"
        accept="video/*"
        onChange={handleInputChange}
        className="hidden"
        id="video-upload-input"
      />

      <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
        <div
          className={cn(
            "mb-4 rounded-full p-4 transition-colors",
            isDragging ? "bg-primary/10" : "bg-muted"
          )}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="32"
            height="32"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={cn(
              "transition-colors",
              isDragging ? "text-primary" : "text-muted-foreground"
            )}
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" x2="12" y1="3" y2="15" />
          </svg>
        </div>

        <h3 className="text-lg font-semibold">
          {isDragging ? "Drop your video here" : "Upload a video"}
        </h3>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          Drag and drop your video, or click to browse. Supports MP4, MOV, WebM,
          AVI, and MKV {isFree ? "up to 500MB and 30 mins" : "up to 2GB"}.
        </p>

        {error && (
          <div className="mt-4 rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
            {error}
            <Button
              variant="ghost"
              size="sm"
              className="ml-2 h-auto p-0 text-destructive underline"
              onClick={(e) => {
                e.stopPropagation()
                reset()
                setSelectedFile(null)
              }}
            >
              Try again
            </Button>
          </div>
        )}

        {!error && (
          <Button variant="secondary" className="mt-6" id="browse-files-btn">
            Browse files
          </Button>
        )}
      </div>
    </div>
  )
}
