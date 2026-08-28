"use server"

import { requireAuth } from "@/lib/auth-server"
import { db } from "@/lib/db"
import { user, clips, WatermarkConfig } from "@/lib/db/schema"
import { eq } from "drizzle-orm"
import { uploadFileToR2 } from "@/lib/r2"
import crypto from "crypto"

export async function uploadWatermarkLogoAction(formData: FormData) {
  const session = await requireAuth()
  const file = formData.get("file") as File | null

  if (!file) {
    throw new Error("No file provided")
  }

  const validTypes = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/svg+xml"]
  if (!validTypes.includes(file.type)) {
    throw new Error("Invalid file type. Only PNG, JPEG, WebP, and SVG images are allowed.")
  }

  const bytes = await file.arrayBuffer()
  const buffer = Buffer.from(bytes)

  const ext = file.name.split(".").pop() || "png"
  const key = `watermarks/${session.user.id}/${crypto.randomUUID()}.${ext}`

  const imageUrl = await uploadFileToR2(key, buffer, file.type)

  // Fetch current user config to merge
  const [userData] = await db
    .select({ watermarkConfig: user.watermarkConfig, plan: user.plan })
    .from(user)
    .where(eq(user.id, session.user.id))

  const existingConfig: WatermarkConfig = userData?.watermarkConfig || {
    enabled: true,
    position: "top-left",
    opacity: 0.7,
    scale: 0.15,
  }

  const updatedConfig: WatermarkConfig = {
    ...existingConfig,
    enabled: true,
    imageUrl,
  }

  await db
    .update(user)
    .set({
      watermarkConfig: updatedConfig,
      updatedAt: new Date(),
    })
    .where(eq(user.id, session.user.id))

  return {
    success: true,
    imageUrl,
    config: updatedConfig,
  }
}

export async function updateUserWatermarkConfigAction(
  configUpdate: Partial<WatermarkConfig>
) {
  const session = await requireAuth()

  const [userData] = await db
    .select({ watermarkConfig: user.watermarkConfig })
    .from(user)
    .where(eq(user.id, session.user.id))

  const existingConfig: WatermarkConfig = userData?.watermarkConfig || {
    enabled: true,
    position: "top-left",
    opacity: 0.7,
    scale: 0.15,
  }

  const newConfig: WatermarkConfig = {
    ...existingConfig,
    ...configUpdate,
  }

  await db
    .update(user)
    .set({
      watermarkConfig: newConfig,
      updatedAt: new Date(),
    })
    .where(eq(user.id, session.user.id))

  return {
    success: true,
    config: newConfig,
  }
}

export async function updateClipWatermarkConfigAction(
  clipId: string,
  configUpdate: Partial<WatermarkConfig>
) {
  await requireAuth()

  const [clipData] = await db
    .select({ watermarkConfig: clips.watermarkConfig })
    .from(clips)
    .where(eq(clips.id, clipId))

  if (!clipData) {
    throw new Error("Clip not found")
  }

  const existingConfig: WatermarkConfig = clipData.watermarkConfig || {
    enabled: true,
    position: "top-left",
    opacity: 0.7,
    scale: 0.15,
  }

  const newConfig: WatermarkConfig = {
    ...existingConfig,
    ...configUpdate,
  }

  await db
    .update(clips)
    .set({
      watermarkConfig: newConfig,
      updatedAt: new Date(),
    })
    .where(eq(clips.id, clipId))

  return {
    success: true,
    config: newConfig,
  }
}

export async function getUserWatermarkConfigAction() {
  const session = await requireAuth()

  const [userData] = await db
    .select({ watermarkConfig: user.watermarkConfig, plan: user.plan })
    .from(user)
    .where(eq(user.id, session.user.id))

  return {
    config: userData?.watermarkConfig || null,
    plan: userData?.plan || "free",
  }
}
