"use client"

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Pencil } from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

export function EditableTitle({
  projectId,
  value,
  onSaved,
}: {
  projectId: string
  value: string
  onSaved: (newTitle: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const headingRef = useRef<HTMLHeadingElement | null>(null)
  const cancelledRef = useRef(false)

  useEffect(() => {
    if (headingRef.current && !editing) {
      headingRef.current.innerText = value
    }
  }, [value, editing])

  useEffect(() => {
    if (editing && headingRef.current) {
      headingRef.current.focus()
      // Move cursor to end of text
      const range = document.createRange()
      const sel = window.getSelection()
      range.selectNodeContents(headingRef.current)
      range.collapse(false)
      sel?.removeAllRanges()
      sel?.addRange(range)
    }
  }, [editing])

  const commit = async () => {
    if (!headingRef.current) return
    if (cancelledRef.current) {
      cancelledRef.current = false
      setEditing(false)
      headingRef.current.innerText = value
      return
    }

    const draft = headingRef.current.innerText.trim()
    if (!draft || draft === value) {
      setEditing(false)
      headingRef.current.innerText = value
      return
    }

    setIsSaving(true)
    try {
      const res = await fetch(`/api/projects/${projectId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: draft }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.error || "Failed to update title")
      }
      const data = await res.json()
      onSaved(data.project.title)
      setEditing(false)
    } catch (err) {
      console.error("Title update failed:", err)
      toast.error("Couldn't update title")
      headingRef.current.innerText = value
      setEditing(false)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="group/title flex min-w-0 items-center gap-1.5">
      <h1
        ref={headingRef}
        contentEditable={!isSaving}
        suppressContentEditableWarning
        onFocus={() => setEditing(true)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault()
            headingRef.current?.blur()
          } else if (e.key === "Escape") {
            e.preventDefault()
            cancelledRef.current = true
            headingRef.current?.blur()
          }
        }}
        title="Click to edit title"
        className={cn(
          "min-w-0 text-lg font-bold tracking-tight break-words text-slate-900 sm:text-xl outline-hidden transition-all cursor-text border-b pb-0.5",
          editing ? "border-slate-200" : "border-transparent hover:border-slate-100"
        )}
      >
        {value}
      </h1>
      {!editing && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => headingRef.current?.focus()}
          title="Rename"
          aria-label="Rename project"
          className="h-8 w-8 shrink-0 rounded-lg text-slate-400 opacity-60 transition-all group-hover/title:opacity-100 hover:bg-primary/5 hover:text-primary focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:outline-none"
        >
          <Pencil className="h-4 w-4" />
        </Button>
      )}
    </div>
  )
}
