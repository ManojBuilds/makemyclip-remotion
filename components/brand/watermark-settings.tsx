"use client"

import React, { useState, useEffect, useTransition } from "react"
import { WatermarkConfig } from "@/lib/db/schema"
import {
  uploadWatermarkLogoAction,
  updateUserWatermarkConfigAction,
  getUserWatermarkConfigAction,
} from "@/lib/actions/watermark"
import { WatermarkReelPreview } from "./watermark-reel-preview"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import {
  Upload,
  Image as ImageIcon,
  Lock,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Save,
} from "lucide-react"

interface WatermarkSettingsProps {
  initialConfig: WatermarkConfig | null
  userPlan?: string
}

export function WatermarkSettings({
  initialConfig,
  userPlan = "free",
}: WatermarkSettingsProps) {
  const isFreePlan = userPlan === "free"

  const [config, setConfig] = useState<WatermarkConfig>({
    enabled: initialConfig?.enabled ?? true,
    imageUrl: initialConfig?.imageUrl || "",
    position: initialConfig?.position || "top-left",
    opacity: initialConfig?.opacity ?? 0.7,
    scale: initialConfig?.scale ?? 0.15,
  })

  // Autoload saved watermark configuration from DB
  useEffect(() => {
    async function loadSavedConfig() {
      try {
        const res = await getUserWatermarkConfigAction()
        if (res.config) {
          setConfig({
            enabled: res.config.enabled ?? true,
            imageUrl: res.config.imageUrl || "",
            position: res.config.position || "top-left",
            opacity: res.config.opacity ?? 0.7,
            scale: res.config.scale ?? 0.15,
          })
        }
      } catch (err) {
        console.error("Failed to load user watermark config:", err)
      }
    }
    loadSavedConfig()
  }, [])

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null)

  const handleLogoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const validTypes = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/svg+xml"]
    if (!validTypes.includes(file.type)) {
      setFeedback({
        type: "error",
        message: "Invalid file type. Only PNG, SVG, JPEG, and WebP are allowed.",
      })
      return
    }

    setSelectedFile(file)
    setFeedback(null)

    const previewUrl = URL.createObjectURL(file)
    setConfig((prev) => ({ ...prev, imageUrl: previewUrl }))
  }

  const updateConfigField = <K extends keyof WatermarkConfig>(
    field: K,
    value: WatermarkConfig[K]
  ) => {
    setConfig((prev) => ({ ...prev, [field]: value }))
  }

  const handleSaveWatermark = async () => {
    setSaving(true)
    setFeedback(null)

    try {
      let finalImageUrl = config.imageUrl

      if (selectedFile) {
        const formData = new FormData()
        formData.append("file", selectedFile)

        const uploadRes = await uploadWatermarkLogoAction(formData)
        if (uploadRes.success && uploadRes.imageUrl) {
          finalImageUrl = uploadRes.imageUrl
        }
      }

      const saveRes = await updateUserWatermarkConfigAction({
        enabled: config.enabled,
        imageUrl: finalImageUrl,
        position: config.position,
        opacity: config.opacity,
        scale: config.scale,
      })

      if (saveRes.success && saveRes.config) {
        setConfig(saveRes.config)
        setSelectedFile(null)
        setFeedback({
          type: "success",
          message: "Watermark settings saved successfully.",
        })
      }
    } catch (err: any) {
      setFeedback({
        type: "error",
        message: err.message || "Failed to save watermark settings.",
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="w-full border-slate-200 bg-white text-slate-900 shadow-sm rounded-xl">
      <CardHeader className="border-b border-slate-100">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg font-bold text-slate-900">
              <ImageIcon className="h-4 w-4 text-slate-600" />
              Brand Watermark
            </CardTitle>
            <CardDescription className="text-xs text-slate-500 mt-1">
              Overlay your custom transparent logo on exported video clips.
            </CardDescription>
          </div>
          {isFreePlan ? (
            <Badge variant="outline" className="w-fit border-amber-200 bg-amber-50 text-amber-800 text-xs font-medium">
              <Lock className="mr-1 h-3 w-3 text-amber-600" /> Creator Plan Required
            </Badge>
          ) : (
            <Badge variant="outline" className="w-fit border-emerald-200 bg-emerald-50 text-emerald-800 text-xs font-semibold">
              Active
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent>
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
          {/* Controls Column */}
          <div className="space-y-6 lg:col-span-7">
            {/* Free Plan Banner */}
            {isFreePlan && (
              <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50/70 p-3.5 text-amber-900">
                <Lock className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-600" />
                <div className="text-xs leading-normal">
                  <p className="font-semibold text-amber-900">Custom Watermarks Locked</p>
                  <p className="mt-0.5 text-amber-700">
                    Free plan clips include MakeMyClip branding. Upgrade to Creator or Pro to use custom logos.
                  </p>
                </div>
              </div>
            )}

            {/* Toggle Enable */}
            <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50/60 p-4">
              <div>
                <Label htmlFor="watermark-toggle" className="text-xs font-semibold text-slate-900">
                  Burn Watermark on Clips
                </Label>
                <p className="text-xs text-slate-500">
                  Overlay custom brand logo on exported videos
                </p>
              </div>
              <Switch
                id="watermark-toggle"
                disabled={isFreePlan}
                checked={config.enabled}
                onCheckedChange={(checked) => updateConfigField("enabled", checked)}
              />
            </div>

            {/* Logo Image Picker */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold text-slate-800">
                Logo Asset (PNG or SVG format recommended)
              </Label>
              <div className="flex items-center gap-4">
                {config.imageUrl ? (
                  <div className="relative flex h-16 w-16 items-center justify-center rounded-lg border border-slate-200 p-2 shadow-inner">
                    {/* eslint-disable-next-html-element-suppression */}
                    <img
                      src={config.imageUrl}
                      alt="Logo preview"
                      className="h-full w-full object-contain"
                    />
                  </div>
                ) : (
                  <div className="flex h-16 w-16 items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 text-slate-400">
                    <ImageIcon className="h-5 w-5" />
                  </div>
                )}

                <div className="flex-1 space-y-1">
                  <label htmlFor="watermark-file-upload">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={isFreePlan || saving}
                      className="cursor-pointer border-slate-200 bg-slate-50 text-xs text-slate-800 hover:bg-slate-100 shadow-sm"
                      onClick={() => document.getElementById("watermark-file-upload")?.click()}
                    >
                      <Upload className="mr-1.5 h-3.5 w-3.5 text-slate-500" />
                      {selectedFile ? "Change Logo File" : "Select Logo (PNG, SVG)"}
                    </Button>
                  </label>
                  <input
                    id="watermark-file-upload"
                    type="file"
                    accept="image/png,image/svg+xml,image/jpeg,image/webp"
                    className="hidden"
                    onChange={handleLogoSelect}
                    disabled={isFreePlan || saving}
                  />
                  {selectedFile ? (
                    <p className="text-[11px] font-medium text-slate-700">
                      Selected: {selectedFile.name} (Click Save below)
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-500">Max size 10MB. PNG, SVG, JPG, WebP.</p>
                  )}
                </div>
              </div>
            </div>

            {/* Position Picker */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold text-slate-800">Watermark Position (Safe Top Zone)</Label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: "top-left", label: "Top-Left" },
                  { id: "top-right", label: "Top-Right" },
                ].map((pos) => (
                  <Button
                    key={pos.id}
                    type="button"
                    variant={config.position === pos.id ? "default" : "outline"}
                    disabled={isFreePlan}
                    onClick={() => updateConfigField("position", pos.id as any)}
                    className={`h-9 text-xs font-medium transition-colors ${config.position === pos.id
                      ? "bg-slate-900 font-semibold text-white hover:bg-slate-800 shadow-sm"
                      : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
                      }`}
                  >
                    {pos.label}
                  </Button>
                ))}
              </div>
            </div>

            {/* Opacity Slider */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-semibold text-slate-800">Opacity</Label>
                <span className="text-xs font-semibold text-slate-900">
                  {Math.round((config.opacity ?? 0.7) * 100)}%
                </span>
              </div>
              <Slider
                disabled={isFreePlan}
                min={10}
                max={100}
                step={5}
                value={[Math.round((config.opacity ?? 0.7) * 100)]}
                onValueChange={([val]) => updateConfigField("opacity", val / 100)}
                className="py-1"
              />
            </div>

            {/* Scale / Size Slider */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-semibold text-slate-800">Size (Width %)</Label>
                <span className="text-xs font-semibold text-slate-900">
                  {Math.round((config.scale ?? 0.15) * 100)}%
                </span>
              </div>
              <Slider
                disabled={isFreePlan}
                min={5}
                max={30}
                step={1}
                value={[Math.round((config.scale ?? 0.15) * 100)]}
                onValueChange={([val]) => updateConfigField("scale", val / 100)}
                className="py-1"
              />
            </div>

            {/* Feedback Alert */}
            {feedback && (
              <div
                className={`flex items-center gap-2 rounded-lg p-3 text-xs ${feedback.type === "success"
                  ? "border border-emerald-200 bg-emerald-50 text-emerald-900"
                  : "border border-rose-200 bg-rose-50 text-rose-900"
                  }`}
              >
                {feedback.type === "success" ? (
                  <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-emerald-600" />
                ) : (
                  <AlertCircle className="h-4 w-4 flex-shrink-0 text-rose-600" />
                )}
                {feedback.message}
              </div>
            )}

            {/* Save Button */}
            <div className="pt-2">
              <Button
                type="button"
                disabled={isFreePlan || saving}
                onClick={handleSaveWatermark}
                className="w-full bg-slate-900 font-semibold text-white hover:bg-slate-800 shadow-sm"
              >
                {saving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin text-white" /> Saving Settings...
                  </>
                ) : (
                  <>
                    <Save className="mr-2 h-4 w-4" /> Save Watermark Settings
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Reel Preview Column */}
          <div className="flex flex-col items-center justify-center border-t border-slate-100 pt-6 lg:col-span-5 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
            <WatermarkReelPreview config={config} isFreePlan={isFreePlan} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
