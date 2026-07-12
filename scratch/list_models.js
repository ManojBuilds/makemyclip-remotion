import "dotenv/config";
import { GoogleGenAI } from "@google/genai";

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const ai = new GoogleGenAI({ apiKey: GEMINI_API_KEY ?? "" });

async function main() {
  try {
    const list = await ai.models.list();
    console.log("Iterating over models:");
    let count = 0;
    for await (const model of list) {
      count++;
      console.log(`- ${model.name}`);
    }
    console.log("Total models:", count);
  } catch (error) {
    console.error("Error listing models:", error);
  }
}

main();
