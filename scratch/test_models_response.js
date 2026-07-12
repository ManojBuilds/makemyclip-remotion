import "dotenv/config";
import { GoogleGenAI } from "@google/genai";
import fs from "fs";

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const ai = new GoogleGenAI({ apiKey: GEMINI_API_KEY ?? "" });

const CANDIDATES = [
  "gemini-2.5-pro",
  "gemini-2.5-flash",
  "gemini-2.0-flash",
  "gemini-3.5-flash",
  "gemini-3.1-flash-lite",
  "gemini-2.0-flash-lite",
  "gemini-2.5-flash-lite",
  "gemini-flash-latest",
  "gemini-flash-lite-latest",
  "gemini-pro-latest",
];

async function main() {
  let log = "";
  for (const model of CANDIDATES) {
    try {
      log += `Testing model: ${model}...\n`;
      const response = await ai.models.generateContent({
        model,
        contents: "Hello, respond with exactly 'OK'",
      });
      log += `✅ Success for ${model}: "${response.text?.trim()}"\n`;
    } catch (error) {
      log += `❌ Failed for ${model}: ${error.message || error}\n`;
    }
    log += "----------------------------------------\n";
  }
  fs.writeFileSync("scratch/test_results.txt", log, "utf-8");
}

main();
