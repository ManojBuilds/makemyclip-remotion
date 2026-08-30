"use client"

import React from "react"
import { WatermarkConfig } from "@/lib/db/schema"
import { Eye } from "lucide-react"

interface WatermarkReelPreviewProps {
  config: Partial<WatermarkConfig> | null
  isFreePlan?: boolean
}

export function WatermarkReelPreview({
  config,
  isFreePlan = false,
}: WatermarkReelPreviewProps) {
  const enabled = config?.enabled ?? true
  const imageUrl = config?.imageUrl
  const position = config?.position || "top-left"
  const opacity = config?.opacity ?? 0.7
  const scale = config?.scale ?? 0.15

  const getPositionStyle = () => {
    if (position === "top-right") {
      return { top: "1.25rem", right: "1rem" }
    }
    return { top: "1.25rem", left: "1rem" }
  }

  return (
    <div className="relative mx-auto flex w-full max-w-[280px] flex-col items-center">

      {/* 9:16 Mobile Reel Frame Container */}
      <div className="relative aspect-[9/16] w-full overflow-hidden rounded-xl border border-slate-200 bg-slate-100 shadow-md">
        {/* Real Reel Screenshot Background Image */}
        {/* eslint-disable-next-html-element-suppression */}
        <img
          src="https://res.cloudinary.com/dc6yzmwrq/image/upload/v1787917215/reel_screenshot_preview_rlpw86.jpg"
          alt="Reel video frame screenshot"
          className="absolute inset-0 h-full w-full object-cover"
        />

        {/* Watermark Overlay (Free Plan vs Custom Logo) */}
        {isFreePlan ? (
          <div
            style={{ top: "1.25rem", left: "1rem", width: "45%", opacity: 0.7 }}
            className="absolute z-20 pointer-events-none drop-shadow-md"
          >
            {/* eslint-disable-next-html-element-suppression */}
            <img
              src="https://res.cloudinary.com/dc6yzmwrq/image/upload/v1788055153/kivio_watermark_glass_tpypfp.png"
              alt="Default Platform Watermark"
              className="h-auto w-full object-contain filter drop-shadow-md"
            />
          </div>
        ) : enabled && imageUrl ? (
          <div
            style={{
              ...getPositionStyle(),
              width: `${Math.round(scale * 100)}%`,
              opacity: opacity,
            }}
            className="absolute z-20 pointer-events-none transition-all duration-150"
          >
            {/* eslint-disable-next-html-element-suppression */}
            <img
              src={imageUrl}
              alt="Watermark Preview"
              className="h-auto w-full object-contain filter drop-shadow-md"
            />
          </div>
        ) : enabled ? (
          <div
            style={{
              ...getPositionStyle(),
              opacity: 0.85,
            }}
            className="absolute z-20 rounded bg-slate-900/90 px-2 py-1 text-[10px] font-semibold text-white border border-slate-700 shadow-md backdrop-blur-sm"
          >
            Logo Here
          </div>
        ) : null}
      </div>
    </div>
  )
}
