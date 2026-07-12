import { relations } from "drizzle-orm"
import {
  pgTable,
  text,
  timestamp,
  boolean,
  real,
  integer,
  jsonb,
} from "drizzle-orm/pg-core"
import { createId } from "@paralleldrive/cuid2"

// ─────────────────────────────────────────────
// Better Auth tables (must match better-auth schema)
// ─────────────────────────────────────────────

export const user = pgTable("user", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  email: text("email").notNull().unique(),
  emailVerified: boolean("email_verified").notNull().default(false),
  image: text("image"),
  dodoCustomerId: text("dodo_customer_id"),
  subscriptionStatus: text("subscription_status").default("inactive"),
  plan: text("plan").default("free"),
  credits: integer("credits").default(30),
  createdAt: timestamp("created_at").notNull().defaultNow(),
  updatedAt: timestamp("updated_at").notNull().defaultNow(),
})

export const session = pgTable("session", {
  id: text("id").primaryKey(),
  expiresAt: timestamp("expires_at").notNull(),
  token: text("token").notNull().unique(),
  createdAt: timestamp("created_at").notNull().defaultNow(),
  updatedAt: timestamp("updated_at").notNull().defaultNow(),
  ipAddress: text("ip_address"),
  userAgent: text("user_agent"),
  userId: text("user_id")
    .notNull()
    .references(() => user.id, { onDelete: "cascade" }),
})

export const account = pgTable("account", {
  id: text("id").primaryKey(),
  accountId: text("account_id").notNull(),
  providerId: text("provider_id").notNull(),
  userId: text("user_id")
    .notNull()
    .references(() => user.id, { onDelete: "cascade" }),
  accessToken: text("access_token"),
  refreshToken: text("refresh_token"),
  idToken: text("id_token"),
  accessTokenExpiresAt: timestamp("access_token_expires_at"),
  refreshTokenExpiresAt: timestamp("refresh_token_expires_at"),
  scope: text("scope"),
  password: text("password"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
  updatedAt: timestamp("updated_at").notNull().defaultNow(),
})

export const verification = pgTable("verification", {
  id: text("id").primaryKey(),
  identifier: text("identifier").notNull(),
  value: text("value").notNull(),
  expiresAt: timestamp("expires_at").notNull(),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
})

// ─────────────────────────────────────────────
// App tables
// ─────────────────────────────────────────────

export const projects = pgTable("projects", {
  id: text("id")
    .primaryKey()
    .$defaultFn(() => createId()),
  userId: text("user_id")
    .notNull()
    .references(() => user.id, { onDelete: "cascade" }),
  title: text("title").notNull(),
  status: text("status", {
    enum: ["uploading", "processing", "analyzing", "ready", "error"],
  })
    .notNull()
    .default("uploading"),
  sourceVideoKey: text("source_video_key"),
  sourceAudioKey: text("source_audio_key"),
  duration: real("duration"),
  fps: real("fps"),
  width: integer("width"),
  height: integer("height"),
  errorMessage: text("error_message"),
  // Caption styling (project-level — applies to all clips)
  captionStyle: text("caption_style").default("hormozi"),
  videoFormat: text("video_format").default("reframe"),
  transcribeLanguage: text("transcribe_language").default("auto"),
  translateLanguage: text("translate_language").default("none"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
  updatedAt: timestamp("updated_at").notNull().defaultNow(),
})

export const transcriptions = pgTable("transcriptions", {
  id: text("id")
    .primaryKey()
    .$defaultFn(() => createId()),
  projectId: text("project_id")
    .notNull()
    .references(() => projects.id, { onDelete: "cascade" }),
  fullText: text("full_text"),
  words: jsonb("words").$type<WordTimestamp[]>(),
  paragraphs: jsonb("paragraphs"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
})

export const clips = pgTable("clips", {
  id: text("id")
    .primaryKey()
    .$defaultFn(() => createId()),
  projectId: text("project_id")
    .notNull()
    .references(() => projects.id, { onDelete: "cascade" }),
  title: text("title"),
  hookText: text("hook_text"),
  startTime: real("start_time").notNull(),
  endTime: real("end_time").notNull(),
  viralScore: integer("viral_score"),
  viralReason: text("viral_reason"),
  clipType: text("clip_type"),
  speakerDynamic: text("speaker_dynamic"),
  cropMode: text("crop_mode", {
    enum: ["reframe", "letterbox", "split", "course", "auto"],
  }).default("auto"),
  captionStyle: text("caption_style").notNull().default("hormozi"),
  captions: jsonb("captions").$type<ClipCaption[]>(),
  originalVideoUrl: text("original_video_url"),
  previewVideoUrl: text("preview_video_url"),
  captionVideoUrl: text("caption_video_url"),
  status: text("status", {
    enum: ["detected", "editing", "queued", "rendering", "rendered", "error"],
  })
    .notNull()
    .default("detected"),
  thumbnailUrl: text("thumbnail_url"),
  renderedUrl: text("rendered_url"),
  renderProgress: real("render_progress"),
  renderStatus: text("render_status"),
  lastRenderedAt: timestamp("last_rendered_at"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
  updatedAt: timestamp("updated_at").notNull().defaultNow(),
})

// ─────────────────────────────────────────────
// RELATIONS
// ─────────────────────────────────────────────

export const projectsRelations = relations(projects, ({ many, one }) => ({
  clips: many(clips),
  transcription: one(transcriptions),
}))

export const clipsRelations = relations(clips, ({ one }) => ({
  project: one(projects, {
    fields: [clips.projectId],
    references: [projects.id],
  }),
}))

export const transcriptionsRelations = relations(transcriptions, ({ one }) => ({
  project: one(projects, {
    fields: [transcriptions.projectId],
    references: [projects.id],
  }),
}))

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

export type WordTimestamp = {
  word: string
  start: number
  end: number
  confidence: number
  speaker?: number
}

export type FaceKeyframe = {
  time: number
  faces: { x: number; y: number; width: number; height: number }[]
}

export type ReframeKeyframe = {
  time: number
  cropX: number
  cropY: number
  cropW: number
  cropH: number
  strategy?: "TRACK" | "LETTERBOX"
}

export type ClipCaption = {
  id: string
  transcript: string
  start: number
  end: number
  confidence: number
  channel: number
  words: {
    word: string
    punctuated_word: string
    start: number
    end: number
    confidence: number
  }[]
}
