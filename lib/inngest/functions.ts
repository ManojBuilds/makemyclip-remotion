import { inngest } from "./client"
import { db } from "@/lib/db"
import { projects, transcriptions, clips, user } from "@/lib/db/schema"
import type { WordTimestamp, ClipCaption } from "@/lib/db/schema"
import { eq, inArray, sql } from "drizzle-orm"
import { getDownloadPresignedUrl } from "@/lib/r2"
import {
  submitTranscription,
  getAssemblyAiStatus,
  enrichTranscript,
  transcribeFromUrl,
} from "@/lib/assemblyai"
import { isHttpUrl, normalizeVideoUrl } from "@/lib/youtube"
import {
  trackServerVideoAnalysisCompleted,
  trackServerClipRenderCompleted,
} from "@/lib/posthog-server"

async function resolveSourceVideoUrl(
  sourceVideoKeyOrUrl: string,
  expiresInSeconds: number
) {
  if (isHttpUrl(sourceVideoKeyOrUrl)) return normalizeVideoUrl(sourceVideoKeyOrUrl)
  return getDownloadPresignedUrl(sourceVideoKeyOrUrl, expiresInSeconds)
}

/**
 * Main background function that handles the video processing pipeline.
 * Triggered when a video is successfully uploaded to R2.
 */
export const processVideo = inngest.createFunction(
  { id: "process-video", triggers: [{ event: "video.uploaded" }] },
  async ({ event, step }) => {
    const { projectId, key, duration, videoUrl } = event.data
    console.log(
      `[processVideo] Starting for projectId: ${projectId}, key: ${key}`
    )

    // Step 1: Update status to processing and fetch user plan
    const { userPlan, projectStyling, transcribeLanguage, translateLanguage, removeSilence } =
      await step.run("update-status-and-fetch-plan", async () => {
        console.log(
          `[processVideo] Step: update-status-and-fetch-plan for project: ${projectId}`
        )
        const [[data], _] = await Promise.all([
          db
            .select({
              project: projects,
              userPlan: user.plan,
            })
            .from(projects)
            .innerJoin(user, eq(projects.userId, user.id))
            .where(eq(projects.id, projectId)),
          db
            .update(projects)
            .set({ status: "processing" })
            .where(eq(projects.id, projectId))
        ])

        if (!data || !data.project) {
          throw new Error(`Project not found: ${projectId}`);
        }
        const projectData = data.project;

        // Read styling preset from the project record (saved during upload)
        const styling = {
          preset: projectData.captionStyle || "impact",
          word_highlight: projectData.wordHighlight ?? true,
        }

        console.log(
          `[processVideo] User Plan: ${data.userPlan}, Styling Loaded: ${!!styling}, Remove Silence: ${projectData.removeSilence}`
        )
        return {
          userPlan: data.userPlan || "free",
          projectStyling: styling,
          transcribeLanguage: projectData.transcribeLanguage || "auto",
          translateLanguage: projectData.translateLanguage || "none",
          removeSilence: projectData.removeSilence ?? true,
        }
      })

    // Step 2: Check if transcription already exists
    const existingTranscription = await step.run("check-existing-transcription", async () => {
      const existingPromise = db
        .select()
        .from(transcriptions)
        .where(eq(transcriptions.projectId, projectId))
        .limit(1)

      const existingForSameKeyPromise = key
        ? db
          .select({
            fullText: transcriptions.fullText,
            words: transcriptions.words,
            paragraphs: transcriptions.paragraphs,
          })
          .from(transcriptions)
          .innerJoin(projects, eq(transcriptions.projectId, projects.id))
          .where(eq(projects.sourceVideoKey, key))
          .limit(1)
        : Promise.resolve([])

      const [existing, existingForSameKeyList] = await Promise.all([
        existingPromise,
        existingForSameKeyPromise
      ])

      if (existing.length > 0) {
        console.log(
          `[processVideo] Transcription already exists for project ${projectId}. Skipping new transcription.`
        )
        return {
          fullText: existing[0].fullText,
          words: existing[0].words as WordTimestamp[],
          paragraphs: existing[0].paragraphs,
          viralClips: undefined as any[] | undefined,
        }
      }

      if (key && existingForSameKeyList?.length > 0) {
        const existingForSameKey = existingForSameKeyList[0]
        console.log(
          `[processVideo] Transcription found in another project with the same key: ${key}. Reusing it.`
        )
        await db.insert(transcriptions).values({
          projectId,
          fullText: existingForSameKey.fullText,
          words: existingForSameKey.words,
          paragraphs: existingForSameKey.paragraphs,
        })
        return {
          fullText: existingForSameKey.fullText,
          words: existingForSameKey.words as WordTimestamp[],
          paragraphs: existingForSameKey.paragraphs,
          viralClips: undefined as any[] | undefined,
        }
      }

      return null
    })

    const runVideoAnalysis = async () => {
      return await step.run("analyze-video-modal", async () => {
        const analyzerEndpoint = process.env.MODAL_ANALYZER_ENDPOINT || "https://ms8460149--makemyclip-ai-rendering-videoanalyzer-analyze.modal.run"
        console.log(`[processVideo] Step: analyze-video-modal calling endpoint: ${analyzerEndpoint}`)

        const projPromise = db
          .select({ analysisPath: projects.analysisPath })
          .from(projects)
          .where(eq(projects.id, projectId))
          .then(res => res[0])

        const existingAnalysisPromise = key
          ? db
            .select({ analysisPath: projects.analysisPath })
            .from(projects)
            .where(eq(projects.sourceVideoKey, key))
            .limit(1)
            .then(res => res[0])
          : Promise.resolve(null)

        const [proj, existingAnalysis] = await Promise.all([
          projPromise,
          existingAnalysisPromise
        ])

        if (proj?.analysisPath) {
          console.log(`[processVideo] Analysis path already exists for project ${projectId}: ${proj.analysisPath}. Skipping analyze-video-modal.`)
          return { success: true, analysisUrl: proj.analysisPath }
        }

        if (key && existingAnalysis?.analysisPath) {
          console.log(`[processVideo] Analysis path found in another project with the same key: ${key}. Reusing it.`)
          await db
            .update(projects)
            .set({
              analysisPath: existingAnalysis.analysisPath,
            })
            .where(eq(projects.id, projectId))
          return { success: true, analysisUrl: existingAnalysis.analysisPath }
        }

        const presignedUrl = videoUrl || (await getDownloadPresignedUrl(key, 3600))
        const videoDuration = duration || 600

        try {
          const response = await fetch(analyzerEndpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              video_url: presignedUrl,
              project_id: projectId,
              duration: videoDuration,
              detect_skip: 5,
            }),
          })

          if (!response.ok) {
            const errText = await response.text()
            console.error(`[processVideo] Modal VideoAnalyzer failed with status ${response.status}: ${errText}`)
            throw new Error(`VideoAnalyzer failed with status ${response.status}: ${errText}`)
          }

          const resJson = await response.json()
          if (resJson.success && resJson.analysis_url) {
            console.log(`[processVideo] Saved analysis.json to R2: ${resJson.analysis_url}`)
            await db
              .update(projects)
              .set({
                analysisPath: resJson.analysis_url,
              })
              .where(eq(projects.id, projectId))
            return { success: true, analysisUrl: resJson.analysis_url }
          }

          throw new Error(resJson.error || "Modal VideoAnalyzer failed to produce analysis.json")
        } catch (error) {
          await db.update(projects).set({ status: "error" }).where(eq(projects.id, projectId))
          throw error
        }
      })
    }

    let transcription: {
      fullText: string
      words: WordTimestamp[]
      paragraphs: string[]
      viralClips?: any[]
    }

    if (existingTranscription) {
      transcription = {
        fullText: existingTranscription.fullText || "",
        words: (existingTranscription.words || []) as WordTimestamp[],
        paragraphs: (existingTranscription.paragraphs as string[]) || [],
        viralClips: existingTranscription.viralClips,
      }
      await runVideoAnalysis()
    } else {
      const presignedUrl = videoUrl || (await getDownloadPresignedUrl(key, 3600))

      // 1. Submit transcription to AssemblyAI (asynchronous, non-blocking, takes ~5-15s)
      const { transcriptId } = await step.run("submit-transcription", async () => {
        console.log(
          `📡 [processVideo][submit-transcription] Submitting audio for project ${projectId} (lang=${transcribeLanguage}, translate=${translateLanguage})...`
        )
        const t0 = Date.now()
        const res = await submitTranscription(
          presignedUrl,
          transcribeLanguage,
          translateLanguage
        )
        console.log(
          `✅ [processVideo][submit-transcription] Job accepted in ${(Date.now() - t0) / 1000}s! Transcript ID: ${res.transcriptId} (initial status: ${res.status})`
        )
        return res
      })

      // 2. Start video analysis in parallel
      console.log(`🎬 [processVideo] Triggering video analysis concurrently...`)
      const videoAnalysisPromise = runVideoAnalysis()

      // 3. Non-blocking sleep polling loop for AssemblyAI (supports 2+ hours safely!)
      let transcriptStatus = "queued"
      let attempts = 0
      const maxAttempts = 120 // 120 * 20s = 40 minutes polling window

      console.log(
        `⏳ [processVideo][polling] Starting non-blocking polling loop for transcript: ${transcriptId}...`
      )

      while (transcriptStatus !== "completed" && attempts < maxAttempts) {
        attempts++
        console.log(
          `💤 [processVideo][polling] Sleeping 20s before poll attempt #${attempts} (elapsed: ~${(attempts - 1) * 20}s)...`
        )
        await step.sleep(`wait-transcription-${attempts}`, "20s")

        const pollResult = await step.run(
          `check-transcription-status-${attempts}`,
          async () => {
            const check = await getAssemblyAiStatus(transcriptId)
            console.log(
              `🔍 [processVideo][polling] Poll #${attempts}: status="${check.status}" (elapsed: ~${attempts * 20}s)`
            )
            return check
          }
        )

        transcriptStatus = pollResult.status
        if (transcriptStatus === "error") {
          console.error(`❌ [processVideo][polling] AssemblyAI error: ${pollResult.error}`)
          throw new Error(
            `AssemblyAI transcription failed: ${pollResult.error || "Unknown error"}`
          )
        }
      }

      if (transcriptStatus !== "completed") {
        throw new Error(
          `AssemblyAI transcription timed out after ${maxAttempts * 20}s for transcript ID: ${transcriptId}`
        )
      }

      console.log(
        `🎉 [processVideo][polling] AssemblyAI transcription COMPLETED in ~${attempts * 20}s! Proceeding to enrichment...`
      )

      // 4. Fast transcript & viral clips enrichment (Modal, ~5-15s)
      const enrichedResult = await step.run("enrich-transcription", async () => {
        console.log(
          `🧠 [processVideo][enrich-transcription] Calling Modal to calculate velocity, acoustic events, viral scores & Gemini metadata...`
        )
        const t0 = Date.now()
        const result = await enrichTranscript(transcriptId, translateLanguage)
        console.log(
          `✨ [processVideo][enrich-transcription] Enriched in ${(Date.now() - t0) / 1000}s! Found ${result.viralClips?.length ?? 0} viral clips, ${result.words.length} words.`
        )

        // Persist the transcription to the database
        await db.insert(transcriptions).values({
          projectId,
          fullText: result.fullText,
          words: result.words,
          paragraphs: result.paragraphs,
        })
        console.log(`💾 [processVideo][enrich-transcription] Saved transcription to DB for project ${projectId}`)

        return result
      })

      // Await video analysis to finish before proceeding to save clips & batch reframe
      console.log(`⏳ [processVideo] Ensuring video analysis completes...`)
      await videoAnalysisPromise
      console.log(`✅ [processVideo] Video analysis finished!`)

      transcription = enrichedResult
    }

    const aiClips = await step.run("save-clips-db", async () => {
      console.log(`💾 [processVideo] Step: save-clips-db saving ${transcription.viralClips?.length ?? 0} clips to DB...`)

      const { clips } = await import("@/lib/db/schema")
      const { createId } = await import("@paralleldrive/cuid2")

      const rawClips: any[] = transcription.viralClips || []
      console.log(
        `[processVideo] Modal transcribe step returned ${rawClips.length} pre-enriched viral clips`
      )

      if (!rawClips || rawClips.length === 0) {
        console.warn(
          `[processVideo] WARNING: Modal transcription returned 0 clips. No clips to save.`
        )
        return []
      }

      const insertedClips = await db
        .insert(clips)
        .values(
          rawClips.map((clip: any) => {
            const startSec =
              clip.startTime !== undefined
                ? Number(clip.startTime)
                : Number(clip.start_ms || 0) / 1000.0
            const endSec =
              clip.endTime !== undefined
                ? Number(clip.endTime)
                : Number(clip.end_ms || 0) / 1000.0
            const rawScore = Number(clip.viral_score || clip.viralScore || 85)
            const normalizedScore = Number(
              Math.min(100, Math.max(1, rawScore > 10 ? rawScore : rawScore * 10)).toFixed(0)
            )

            const clipWords = transcription.words
              .filter(
                (w: WordTimestamp) => w.end >= startSec && w.start <= endSec
              )
              .map((w: WordTimestamp) => ({
                word: w.word.replace(/[.,!?]$/, "").toLowerCase(),
                punctuated_word: w.word,
                start: Math.max(0, w.start - startSec),
                end: Math.max(0, w.end - startSec),
                confidence: w.confidence || 0.99,
                speaker: w.speaker?.toString() || "0",
              }))

            const captions = [
              {
                id: createId(),
                transcript: clipWords.map((w) => w.punctuated_word).join(" "),
                start: 0,
                end: Math.max(0, endSec - startSec),
                confidence: 0.99,
                channel: 0,
                words: clipWords,
              },
            ]

            return {
              projectId,
              title: clip.title || clip.headline || "Viral Short Highlight",
              hookText: clip.hookText || clip.hook_quote || "Watch this",
              startTime: startSec,
              endTime: endSec,
              viralScore: Math.round(normalizedScore),
              viralReason:
                clip.viralReason ||
                clip.signals?.pacing_note ||
                "High viral potential.",
              description:
                clip.description ||
                clip.summary ||
                "Featured viral short clip.",
              hashtags: clip.hashtags || "#shorts #viral",
              clipType: clip.clipType || "hot_take",
              speakerDynamic:
                clip.speakerDynamic ||
                clip.signals?.pacing_note ||
                "Speaker exchange",
              cropMode: clip.cropMode || "auto",
              status: "rendering" as const,
              captions,
              captionStyle: projectStyling?.preset || "impact",
              wordHighlight: projectStyling?.word_highlight ?? true,
            }
          })
        )
        .returning()

      console.log(
        `[processVideo] Saved ${insertedClips.length} clips directly to DB`
      )
      return insertedClips
    })

    // Step 4: Trigger batch reframer
    if (aiClips && aiClips.length > 0) {
      await step.sendEvent("trigger-batch-reframe", {
        name: "project.batch_reframe_requested",
        data: {
          projectId,
          clipIds: aiClips.map((clip) => clip.id),
          removeSilence,
        },
      })
    }

    // Step 5: Deduct credits and finalize
    await step.run("deduct-credits-and-finalize", async () => {
      const { user } = await import("@/lib/db/schema")
      const [[projectData], _] = await Promise.all([
        db
          .select({
            userId: projects.userId,
            credits: user.credits,
            duration: projects.duration,
          })
          .from(projects)
          .innerJoin(user, eq(projects.userId, user.id))
          .where(eq(projects.id, projectId)),
        db
          .update(projects)
          .set({ status: "ready" })
          .where(eq(projects.id, projectId))
      ])

      if (!projectData) return

      const durationSeconds =
        typeof duration === "number" &&
          Number.isFinite(duration) &&
          duration > 0
          ? duration
          : (projectData.duration ?? 0)
      const durationInMinutes = Math.ceil(durationSeconds / 60)
      if (durationInMinutes <= 0) return

      const currentCredits = projectData.credits || 0
      const newCredits = Math.max(0, currentCredits - durationInMinutes)

      if (currentCredits < durationInMinutes) {
        console.warn(
          `[processVideo] WARNING: User ${projectData.userId} has ${currentCredits} credits but needs ${durationInMinutes}. Setting credits to 0 (race condition guard).`
        )
      }

      await db
        .update(user)
        .set({
          credits: newCredits,
          updatedAt: new Date(),
        })
        .where(eq(user.id, projectData.userId))

      await trackServerVideoAnalysisCompleted({
        distinctId: projectData.userId,
        projectId,
        durationSeconds,
        clipsCount: aiClips?.length ?? 0,
      })
    })

    return { success: true, projectId, clipsCount: aiClips?.length ?? 0 }
  }
)

/**
 * Background function to handle the rendering of a single clip.
 * Triggered by the user from the UI.
 * Follows the official Remotion Vercel Sandbox pattern:
 * https://www.remotion.dev/docs/vercel-sandbox
 */
/**
 * Background function to handle the re-rendering of a single clip when captions/styling change.
 */
export const renderClip = inngest.createFunction(
  {
    id: "render-clip",
    triggers: [{ event: "clip.render_requested" }],
    concurrency: {
      limit: 5, // Must not exceed Inngest plan limit
    },
  },
  async ({ event, step }) => {
    const { clipId, styling } = event.data
    console.log(`[renderClip] Starting for clipId: ${clipId}`)
    if (styling) {
      console.log(
        `[renderClip] Received custom styling in event trigger:`,
        JSON.stringify(styling, null, 2)
      )
    }

    try {
      const { clip, project, transcription, userPlan } = await step.run(
        "fetch-clip-data",
        async () => {
          console.log(
            `[renderClip] Fetching database records for clipId: ${clipId}`
          )
          const [data] = await db
            .select({
              clip: clips,
              project: projects,
              transcription: transcriptions,
              userPlan: user.plan,
            })
            .from(clips)
            .innerJoin(projects, eq(clips.projectId, projects.id))
            .innerJoin(
              transcriptions,
              eq(projects.id, transcriptions.projectId)
            )
            .innerJoin(user, eq(projects.userId, user.id))
            .where(eq(clips.id, clipId))

          if (!data) {
            console.error(
              `[renderClip] Clip or Transcription not found in database for clipId: ${clipId}`
            )
            throw new Error("Clip or Transcription not found")
          }
          console.log(
            `[renderClip] Fetched clip data successfully. ProjectId: ${data.project.id}, Clip Title: "${data.clip.title}"`
          )
          console.log(
            `[renderClip] Clip time range: ${data.clip.startTime}s to ${data.clip.endTime}s (duration: ${data.clip.endTime - data.clip.startTime}s)`
          )
          console.log(
            `[renderClip] Clip DB styling preset: ${data.clip.captionStyle}`
          )
          return data
        }
      )

      const sourceVideoUrl = await resolveSourceVideoUrl(
        project.sourceVideoKey!,
        3600
      )
      console.log(
        `[renderClip] Resolved source video as ${isHttpUrl(project.sourceVideoKey!) ? "external URL" : "R2 presigned URL"} (len=${sourceVideoUrl?.length ?? 0})`
      )

      const result = await step.run("render-on-modal", async () => {
        console.log(`[renderClip] Step: render-on-modal for clipId: ${clipId}`)

        // Resolve styling payload to send to Modal
        const stylingPayload = styling || {
          preset: clip.captionStyle || "impact",
          word_highlight: clip.wordHighlight ?? true,
        }

        console.log(
          `[renderClip] Final styling payload to send to Modal:`,
          JSON.stringify(stylingPayload, null, 2)
        )
        console.log(
          `[renderClip] Transcript payload length: ${clip.captions?.length || 0} caption blocks`
        )
        if (clip.captions && clip.captions.length > 0) {
          console.log(
            `[renderClip] Sample of first caption block:`,
            JSON.stringify(clip.captions[0], null, 2)
          )
        }

        // Determine which endpoint to use
        // If we already have the original reframe, just burn captions (fast)
        // Otherwise, run the full reframe (slow/GPU)
        const endpoint = clip.originalVideoUrl
          ? process.env.MODAL_BURNER_ENDPOINT
          : process.env.MODAL_REFRAME_ENDPOINT

        console.log(`[renderClip] Selected Modal Endpoint: ${endpoint}`)
        console.log(
          `[renderClip] Source Video URL: ${clip.originalVideoUrl || "Presigned S3 URL"}`
        )

        const requestBody = {
          video_url: clip.originalVideoUrl || sourceVideoUrl,
          start_time: clip.startTime,
          end_time: clip.endTime,
          transcript: clip.captions,
          styling: stylingPayload,
          show_watermark: userPlan === "free",
          crop_mode:
            clip.cropMode && clip.cropMode !== "auto"
              ? clip.cropMode
              : project.videoFormat || "auto",
          quality: "preview",
          analysis_url: project.analysisPath || null,
          remove_silence: project.removeSilence ?? true,
        }

        console.log(
          `[renderClip] Request Body sent to Modal (trimmed video_url):`,
          JSON.stringify(
            {
              ...requestBody,
              video_url: requestBody.video_url
                ? requestBody.video_url.substring(0, 100) + "..."
                : null,
            },
            null,
            2
          )
        )

        const response = await fetch(`${endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody),
        })

        if (!response.ok) {
          const errorText = await response.text()
          console.error(
            `[renderClip] Modal render failed. Status: ${response.status}. Error:`,
            errorText
          )
          throw new Error(
            `Modal render failed with status ${response.status}: ${errorText}`
          )
        }

        const resJson = await response.json()
        console.log(
          `[renderClip] Modal response success:`,
          JSON.stringify(resJson, null, 2)
        )
        return resJson
      })

      if (result.success) {
        await step.run("update-status-rendered", async () => {
          const previewUrl = result.url || result.preview_video_url
          const originalUrl = clip.originalVideoUrl || result.original_video_url
          const cropMode = clip.cropMode || result.crop_mode || clip.cropMode
          console.log(
            `[renderClip] Updating DB status to rendered. originalUrl: ${originalUrl}, previewUrl: ${previewUrl}`
          )
          await db
            .update(clips)
            .set({
              status: "rendered",
              originalVideoUrl: originalUrl,
              previewVideoUrl: previewUrl,
              captionVideoUrl: null,
              thumbnailUrl: result.thumbnail_url || clip.thumbnailUrl,
              cropMode: cropMode,
              captions: result.transcript || clip.captions,
              lastRenderedAt: new Date(),
            })
            .where(eq(clips.id, clipId))
        })
      }

      return { success: true, clipId }
    } catch (error) {
      console.error("[render-clip] Failed:", error)
      await step.run("update-status-error", async () => {
        await db
          .update(clips)
          .set({ status: "error" })
          .where(eq(clips.id, clipId))
      })
      throw error
    }
  }
)

export const batchReframeProject = inngest.createFunction(
  {
    id: "batch-reframe-project",
    triggers: [{ event: "project.batch_reframe_requested" }],
    concurrency: {
      limit: 5, // Must not exceed Inngest plan limit
    },
  },
  async ({ event, step }) => {
    const { projectId, clipIds } = event.data
    console.log(`[batchReframeProject] Starting batch reframe for projectId: ${projectId}, clipIds: ${clipIds}`)

    try {
      // Step 1: Fetch project and user plan
      const { project, userPlan, userEmail, userName } = await step.run(
        "fetch-project-data",
        async () => {
          const [data] = await db
            .select({
              project: projects,
              userPlan: user.plan,
              userEmail: user.email,
              userName: user.name,
            })
            .from(projects)
            .innerJoin(user, eq(projects.userId, user.id))
            .where(eq(projects.id, projectId))

          if (!data) throw new Error("Project or user not found")
          return {
            project: data.project,
            userPlan: data.userPlan,
            userEmail: data.userEmail,
            userName: data.userName,
          }
        }
      )

      // Step 2: Fetch all clips in the batch
      const projectClips = await step.run("fetch-clips-data", async () => {
        return await db
          .select()
          .from(clips)
          .where(inArray(clips.id, clipIds))
      })

      if (!projectClips || projectClips.length === 0) {
        console.warn("[batchReframeProject] No clips found to reframe")
        return { success: true, processed: 0 }
      }

      // Step 3: Resolve source video URL
      const sourceVideoUrl = await resolveSourceVideoUrl(
        project.sourceVideoKey!,
        3600
      )

      const batchResult = await step.run("call-modal-batch-reframer", async () => {
        const clipsPayload = projectClips.map((clip) => {
          const stylingPayload = {
            preset: clip.captionStyle || "impact",
            word_highlight: clip.wordHighlight ?? true,
          }

          return {
            clip_id: clip.id,
            start_time: clip.startTime,
            end_time: clip.endTime,
            crop_mode: clip.cropMode || project.videoFormat || "auto",
            transcript: clip.captions,
            styling: stylingPayload,
            show_watermark: userPlan === "free",
            remove_silence: project.removeSilence ?? true,
          }
        })

        const requestBody = {
          video_url: sourceVideoUrl,
          clips: clipsPayload,
          quality: "preview",
          analysis_url: project.analysisPath || null,
        }

        const batchEndpoint = process.env.MODAL_REFRAME_ENDPOINT || "https://ms8460149--makemyclip-ai-rendering-aireframe-batch-reframe.modal.run"
        console.log(`[batchReframeProject] Calling batch reframe endpoint: ${batchEndpoint}`)

        const response = await fetch(batchEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody),
        })

        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(`Batch reframe failed with status ${response.status}: ${errorText}`)
        }

        return await response.json()
      })

      if (!batchResult.success || !batchResult.results) {
        throw new Error("Batch reframe returned failure status")
      }

      // Step 5: Update all clips database records concurrently
      await step.run("update-clips-database", async () => {
        const now = new Date()
        const updatePromises = batchResult.results.map((res: any) => {
          if (res.success) {
            console.log(`[batchReframeProject] Updating clip ${res.clip_id} to rendered`)
            return db
              .update(clips)
              .set({
                status: "rendered",
                originalVideoUrl: res.original_video_url,
                previewVideoUrl: res.preview_video_url,
                thumbnailUrl: res.thumbnail_url,
                cropMode: res.crop_mode,
                captions: res.transcript,
                lastRenderedAt: now,
              })
              .where(eq(clips.id, res.clip_id))
          } else {
            console.error(`[batchReframeProject] Clip ${res.clip_id} processing failed: ${res.error}`)
            return db
              .update(clips)
              .set({ status: "error" })
              .where(eq(clips.id, res.clip_id))
          }
        })
        await Promise.all(updatePromises)
      })

      // Step 6: Send email notification via Resend that clips are ready
      await step.run("send-clips-ready-email", async () => {
        const successfulClipsCount = batchResult.results.filter(
          (res: { success: boolean }) => res.success
        ).length

        if (successfulClipsCount > 0 && userEmail) {
          console.log(
            `[batchReframeProject] Sending clips ready email to ${userEmail} for project ${projectId}...`
          )
          const { sendClipsReadyEmail } = await import("@/lib/email")
          await sendClipsReadyEmail({
            toEmail: userEmail,
            userName: userName || undefined,
            projectTitle: project.title,
            projectId: project.id,
            clipCount: successfulClipsCount,
          })
        }
      })

      return { success: true, processed: batchResult.results.length }
    } catch (error) {
      console.error("[batchReframeProject] Process level failure:", error)
      await step.run("mark-all-clips-error", async () => {
        await db
          .update(clips)
          .set({ status: "error" })
          .where(inArray(clips.id, clipIds))
      })
      throw error
    }
  }
)


/**
 * On-demand HD export function.
 * Triggered when user clicks Download — produces full 1080p captioned video.
 */
export const exportClip = inngest.createFunction(
  {
    id: "export-clip",
    triggers: [{ event: "clip.export_requested" }],
    concurrency: {
      limit: 5, // Must not exceed Inngest plan limit
    },
  },
  async ({ event, step }) => {
    const { clipId, plan: eventPlan } = event.data
    console.log(`[exportClip] Starting HD export for clipId: ${clipId}`)

    try {
      // Step 1: Fetch clip data
      const { clip, project, userPlan } = await step.run(
        "fetch-clip-data",
        async () => {
          const [data] = await db
            .select({
              clip: clips,
              project: projects,
              userPlan: user.plan,
            })
            .from(clips)
            .innerJoin(projects, eq(clips.projectId, projects.id))
            .innerJoin(user, eq(projects.userId, user.id))
            .where(eq(clips.id, clipId))

          if (!data) throw new Error("Clip not found")
          if (!data.clip.originalVideoUrl)
            throw new Error("No reframed video available for export")
          console.log(
            `[exportClip] Clip: "${data.clip.title}", originalVideoUrl exists: ${!!data.clip.originalVideoUrl}`
          )
          return data
        }
      )

      // Use plan from event data (set by /api/export) with DB fallback
      const plan = eventPlan || userPlan || "free"
      console.log(`[exportClip] Resolved plan: ${plan}`)

      // Step 3: Call Modal burner with quality="export" and plan
      const exportResult = await step.run("export-on-modal", async () => {
        const stylingPayload = {
          preset: clip.captionStyle || "impact",
          word_highlight: clip.wordHighlight ?? true,
        }

        const requestBody = {
          video_url: clip.originalVideoUrl,
          transcript: clip.captions,
          styling: stylingPayload,
          show_watermark: plan === "free",
          crop_mode: clip.cropMode || project.videoFormat || "reframe",
          quality: "export",
          plan,
          remove_silence: project.removeSilence ?? true,
        }

        console.log(`[exportClip] Calling Modal burner with quality=export, plan=${plan}`)

        const response = await fetch(`${process.env.MODAL_BURNER_ENDPOINT}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody),
        })

        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(
            `Export burn failed: ${response.status}: ${errorText}`
          )
        }

        const resJson = await response.json()
        console.log(
          `[exportClip] Export response:`,
          JSON.stringify(resJson, null, 2)
        )
        return resJson
      })

      // Step 4: Save HD export URL to DB
      await step.run("update-status-exported", async () => {
        console.log(`[exportClip] Saving captionVideoUrl: ${exportResult.url}`)
        await db
          .update(clips)
          .set({
            status: "rendered",
            captionVideoUrl: exportResult.url,
            lastRenderedAt: new Date(),
          })
          .where(eq(clips.id, clipId))

        if (project?.userId) {
          await trackServerClipRenderCompleted({
            distinctId: project.userId,
            projectId: clip.projectId,
            clipId,
          })
        }
      })

      return { success: true, clipId }
    } catch (error) {
      console.error("[export-clip] Failed:", error)
      await step.run("update-status-error", async () => {
        await db
          .update(clips)
          .set({
            status: "rendered",
            renderStatus: "Export failed",
          })
          .where(eq(clips.id, clipId))
      })
      throw error
    }
  }
)


