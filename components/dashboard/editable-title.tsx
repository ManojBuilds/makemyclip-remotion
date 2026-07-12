"use client"

import { useEffect, useRef, useState } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Pencil } from "lucide-react"
import { toast } from "sonner"

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
  const [draft, setDraft] = useState(value)
  const [isSaving, setIsSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement | null>(null)
  // Escape sets this so the trailing onBlur → commit() bails out instead of
  // saving a stale draft (state updates from setDraft/setEditing in the
  // keydown handler haven't applied yet by the time blur fires).
  const cancelledRef = useRef(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!editing) setDraft(value)
  }, [value, editing])

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  const commit = async () => {
    if (cancelledRef.current) {
      cancelledRef.current = false
      return
    }
    const trimmed = draft.trim()
    if (!trimmed || trimmed === value) {
      setEditing(false)
      setDraft(value)
      return
    }
    setIsSaving(true)
    try {
      const res = await fetch(`/api/projects/${projectId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: trimmed }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.error || "Failed to update title")
      }
      const data = await res.json()
      onSaved(data.project.title)
      toast.success("Title updated")
      setEditing(false)
    } catch (err) {
      console.error("Title update failed:", err)
      toast.error("Couldn't update title")
      setDraft(value)
      setEditing(false)
    } finally {
      setIsSaving(false)
    }
  }

  if (editing) {
    return (
      <Input
        ref={inputRef}
        value={draft}
        disabled={isSaving}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault()
            commit()
          } else if (e.key === "Escape") {
            e.preventDefault()
            cancelledRef.current = true
            setDraft(value)
            setEditing(false)
          }
        }}
        className="h-12 w-full max-w-xl rounded-xl border-slate-200 px-3 text-xl font-bold tracking-tight sm:text-2xl md:text-3xl"
      />
    )
  }

  return (
    <div className="group/title flex min-w-0 items-center gap-1.5">
      <h1
        onDoubleClick={() => setEditing(true)}
        title="Double-click to rename"
        className="min-w-0 text-2xl font-bold tracking-tight break-words text-slate-900 sm:text-3xl"
      >
        {value}
      </h1>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={() => setEditing(true)}
        title="Rename"
        aria-label="Rename project"
        className="h-8 w-8 shrink-0 rounded-lg text-slate-400 opacity-60 transition-all group-hover/title:opacity-100 hover:bg-primary/5 hover:text-primary focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:outline-none"
      >
        <Pencil className="h-4 w-4" />
      </Button>
    </div>
  )
}
