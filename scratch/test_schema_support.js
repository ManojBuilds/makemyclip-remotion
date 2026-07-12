import "dotenv/config";
import { GoogleGenAI, Type } from "@google/genai";

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const ai = new GoogleGenAI({ apiKey: GEMINI_API_KEY ?? "" });

const schema = {
  type: Type.OBJECT,
  properties: {
    answer: { type: Type.STRING },
    confidence: { type: Type.INTEGER },
  },
  required: ["answer", "confidence"],
};

async function main() {
  try {
    console.log("Testing gemini-3.1-flash-lite with responseSchema...");
    const response = await ai.models.generateContent({
      model: "gemini-3.1-flash-lite",
      contents: "Tell me who was the first person to walk on the moon.",
      config: {
        responseMimeType: "application/json",
        responseSchema: schema,
      },
    });
    console.log("Response:", response.text);
  } catch (error) {
    console.error("Error:", error);
  }
}

main();
