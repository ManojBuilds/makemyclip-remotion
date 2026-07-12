import "dotenv/config"
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

import { analyzeViralMoments } from "../lib/gemini"

async function main() {
  const transcriptPath = path.join(__dirname, "podcast_transcript_en.json")
  if (!fs.existsSync(transcriptPath)) {
    console.error(`❌ Error: Transcript not found at ${transcriptPath}`)
    process.exit(1)
  }

  console.log(`Loading transcript from: ${transcriptPath}...`)
  const transcriptData = JSON.parse(fs.readFileSync(transcriptPath, "utf-8"))

  if (!transcriptData.success || !transcriptData.words) {
    console.error("❌ Invalid transcript data")
    process.exit(1)
  }

  console.log("Analyzing viral moments using Gemini...")
  const t0 = Date.now()

  try {
    const suggestions = await analyzeViralMoments(
      transcriptData.fullText,
      transcriptData.words,
      "UFC fighter interview with Nina Drama. Hilarious/fun interview with multiple personalities (regular Josh, Vato, Incredible Hulk)."
    )

    console.log(
      `\n🎉 Analysis completed in ${((Date.now() - t0) / 1000).toFixed(1)}s!`
    )
    console.log(`Found ${suggestions.length} clip suggestions.`)

    const outputPath = path.join(__dirname, "clip_suggestions.json")
    fs.writeFileSync(outputPath, JSON.stringify(suggestions, null, 2), "utf-8")
    console.log(`💾 Saved suggestions to: ${outputPath}\n`)

    // Output formatted suggestions details
    suggestions.forEach((clip, idx) => {
      console.log(`----------------------------------------`)
      console.log(`Clip #${idx + 1}: ${clip.title}`)
      console.log(`Category: ${clip.clipType} | Score: ${clip.viralScore}`)
      console.log(
        `Duration: ${clip.startTime.toFixed(2)}s - ${clip.endTime.toFixed(2)}s (${clip.durationSeconds.toFixed(1)}s)`
      )
      console.log(`Hook Overlay: "${clip.hookText}"`)
      console.log(`Crop Mode: ${clip.cropMode}`)
      console.log(`Speaker Dynamic: ${clip.speakerDynamic}`)
      console.log(`Reason:\n${clip.viralReason}`)
    })
  } catch (error) {
    console.error("❌ Analysis failed:", error)
    process.exit(1)
  }
}

main()
