"use client"

import { useState, useCallback } from "react"
import { trackVideoUploadStarted } from "@/lib/posthog"

type UploadState = {
  status: "idle" | "preparing" | "uploading" | "completing" | "done" | "error"
  progress: number
  error: string | null
  projectId: string | null
}

const PREPARE_PROGRESS = 10 // show immediate feedback while presigning
const UPLOAD_START = 10
const UPLOAD_END = 90
const COMPLETE_PROGRESS = 95 // reserve final jump for "done"

export function useUpload() {
  const [state, setState] = useState<UploadState>({
    status: "idle",
    progress: 0,
    error: null,
    projectId: null,
  })

  const reset = useCallback(() => {
    setState({
      status: "idle",
      progress: 0,
      error: null,
      projectId: null,
    })
  }, [])

  const upload = useCallback(
    async (
      file: File,
      styling?: Record<string, unknown>,
      videoFormat?: string,
      transcribeLanguage?: string,
      translateLanguage?: string
    ) => {
      try {
        setState({
          status: "preparing",
          progress: PREPARE_PROGRESS,
          error: null,
          projectId: null,
        })

        const duration = await new Promise<number>((resolve) => {
          const video = document.createElement("video")
          video.preload = "metadata"
          video.onloadedmetadata = () => {
            resolve(video.duration)
          }
          video.src = URL.createObjectURL(file)
        })

        trackVideoUploadStarted({
          source: "file",
          fileSizeMb: Math.round(file.size / (1024 * 1024)),
          videoDurationEst: Math.round(duration),
        })


        const presignRes = await fetch("/api/upload/presign", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename: file.name,
            contentType: file.type,
            fileSize: file.size,
            duration,
          }),
        })

        if (!presignRes.ok) {
          const err = await presignRes.json()
          throw new Error(
            err.message || err.error || "Failed to get upload URL"
          )
        }

        const { presignedUrl, key } = await presignRes.json()

        // Step 2: Upload directly to R2 with progress tracking
        setState((prev) => ({
          ...prev,
          status: "uploading",
          progress: UPLOAD_START,
        }))

        await new Promise<void>((resolve, reject) => {
          const xhr = new XMLHttpRequest()

          xhr.upload.addEventListener("progress", (e) => {
            if (e.lengthComputable) {
              const raw = e.loaded / e.total
              const scaled = UPLOAD_START + raw * (UPLOAD_END - UPLOAD_START)
              const progress = Math.max(
                UPLOAD_START,
                Math.min(UPLOAD_END, Math.round(scaled))
              )
              setState((prev) => ({ ...prev, progress }))
            }
          })

          xhr.addEventListener("load", () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              resolve()
            } else {
              reject(new Error(`Upload failed with status ${xhr.status}`))
            }
          })

          xhr.addEventListener("error", () => {
            reject(new Error("Upload failed — network error"))
          })

          xhr.addEventListener("abort", () => {
            reject(new Error("Upload cancelled"))
          })

          xhr.open("PUT", presignedUrl)
          xhr.setRequestHeader("Content-Type", file.type)
          xhr.send(file)
        })

        // Step 3: Confirm upload and create project
        setState((prev) => ({
          ...prev,
          status: "completing",
          progress: COMPLETE_PROGRESS,
        }))

        const title = file.name.replace(/\.[^/.]+$/, "") // Strip extension for title

        const completeRes = await fetch("/api/upload/complete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            key,
            title,
            duration,
            styling,
            videoFormat,
            transcribeLanguage,
            translateLanguage,
          }),
        })

        if (!completeRes.ok) {
          const err = await completeRes.json()
          throw new Error(err.error || "Failed to create project")
        }

        const { projectId } = await completeRes.json()

        setState({
          status: "done",
          progress: 100,
          error: null,
          projectId,
        })

        return projectId
      } catch (error) {
        const message = error instanceof Error ? error.message : "Upload failed"
        setState((prev) => ({
          ...prev,
          status: "error",
          error: message,
        }))
        throw error
      }
    },
    []
  )

  return { ...state, upload, reset }
}
