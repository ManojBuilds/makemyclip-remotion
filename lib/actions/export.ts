"use server"

import { inngest } from "@/lib/inngest/client"
import { db } from "@/lib/db"
import { clips } from "@/lib/db/schema"
import { eq } from "drizzle-orm"

export async function triggerHDExport(clipId: string) {
  if (!clipId) {
    throw new Error("clipId is required")
  }

  const clip = await db.query.clips.findFirst({
    where: eq(clips.id, clipId),
  })

  if (!clip) {
    throw new Error("Clip not found")
  }

  if (!clip.originalVideoUrl) {
    throw new Error(
      "Clip has no reframed video yet. Please wait for processing to complete."
    )
  }

  // If HD export already exists, return it immediately
  if (clip.captionVideoUrl) {
    return {
      success: true,
      alreadyExported: true,
      url: clip.captionVideoUrl,
    }
  }

  // Trigger Inngest export function directly
  await inngest.send({
    name: "clip.export_requested",
    data: { clipId },
  })

  return {
    success: true,
    message: "HD export queued successfully",
  }
}
