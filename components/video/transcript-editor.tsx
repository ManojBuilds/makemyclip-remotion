"use client"

import React, { useState, useRef, useEffect, useMemo, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Search,
  Replace,
  Edit3,
  Check,
  Sparkles,
  X,
  Play,
  FileText,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { ClipCaption } from "@/lib/db/schema"
import { toast } from "sonner"

export interface CaptionWord {
  word: string
  punctuated_word: string
  start: number
  end: number
  confidence: number
  speaker?: string
  layout?: string
}

interface SentenceBlock {
  id: string
  start: number
  end: number
  words: CaptionWord[]
  rawText: string
}

interface TranscriptEditorProps {
  captions: ClipCaption[] | null | undefined
  currentTime: number
  onSeek: (seconds: number) => void
  onPlaySnippet?: (start: number, end: number) => void
  onCaptionsChange: (newCaptions: ClipCaption[]) => void
  clipStartTime?: number
  clipEndTime?: number
}

function formatTimecode(secs: number): string {
  if (isNaN(secs) || secs < 0) return "0s"
  if (secs >= 60) {
    const m = Math.floor(secs / 60)
    const s = Math.floor(secs % 60)
    return `${m}m ${s}s`
  }
  return `${secs.toFixed(1)}s`
}

export function TranscriptEditor({
  captions,
  currentTime,
  onSeek,
  onPlaySnippet,
  onCaptionsChange,
  clipStartTime = 0,
  clipEndTime = 0,
}: TranscriptEditorProps) {
  // Extract flat list of words from captions
  const initialWords: CaptionWord[] = useMemo(() => {
    if (!captions || captions.length === 0) return []
    const list: CaptionWord[] = []
    for (const block of captions) {
      if (Array.isArray(block.words)) {
        for (const w of block.words) {
          list.push({
            word: w.word || "",
            punctuated_word: w.punctuated_word || w.word || "",
            start: Number(w.start) || 0,
            end: Number(w.end) || 0,
            confidence: Number(w.confidence) || 0.99,
            speaker: (w as any).speaker?.toString() || "0",
            layout: (w as any).layout || (block as any).layout,
          })
        }
      }
    }
    return list
  }, [captions])

  const [words, setWords] = useState<CaptionWord[]>(initialWords)
  const [editingBlockId, setEditingBlockId] = useState<string | null>(null)
  const [editingBlockText, setEditingBlockText] = useState<string>("")

  // Inline single-word editing state (simple in-place text edit on double-click without input box)
  const [inlineEditIdx, setInlineEditIdx] = useState<number | null>(null)

  useEffect(() => {
    if (inlineEditIdx !== null) {
      const el = document.getElementById(`word_span_${inlineEditIdx}`)
      if (el) {
        el.focus()
        const range = document.createRange()
        range.selectNodeContents(el)
        const sel = window.getSelection()
        sel?.removeAllRanges()
        sel?.addRange(range)
      }
    }
  }, [inlineEditIdx])

  // Search & Replace bar state
  const [showSearch, setShowSearch] = useState<boolean>(false)
  const [searchQuery, setSearchQuery] = useState<string>("")
  const [replaceQuery, setReplaceQuery] = useState<string>("")

  const activeWordElemRef = useRef<HTMLSpanElement | null>(null)
  const documentContainerRef = useRef<HTMLDivElement | null>(null)

  const [prevCaptions, setPrevCaptions] = useState(captions)
  if (captions !== prevCaptions) {
    setPrevCaptions(captions)
    setWords(initialWords)
  }

  // Broadcast updates up to parent captions structure
  const updateParentCaptions = useCallback(
    (updatedWords: CaptionWord[]) => {
      const sorted = [...updatedWords].sort((a, b) => a.start - b.start)
      setWords(sorted)

      const fullTranscript = sorted.map((w) => w.punctuated_word).join(" ")
      const start = sorted.length > 0 ? sorted[0].start : 0
      const end = sorted.length > 0 ? sorted[sorted.length - 1].end : 0

      const defaultBlockLayout =
        (captions?.[0] as any)?.layout || sorted[0]?.layout

      const updatedCaptions: ClipCaption[] = [
        {
          id: captions?.[0]?.id || "cap_1",
          transcript: fullTranscript,
          start,
          end,
          confidence: 0.99,
          channel: 0,
          layout: defaultBlockLayout,
          words: sorted.map((w) => ({
            ...w,
            layout: w.layout || defaultBlockLayout,
          })),
        } as any,
      ]

      onCaptionsChange(updatedCaptions)
    },
    [captions, onCaptionsChange]
  )

  // Group words into document-like sentence blocks
  const sentenceBlocks: SentenceBlock[] = useMemo(() => {
    if (words.length === 0) return []
    const blocks: SentenceBlock[] = []
    let currentWords: CaptionWord[] = []
    let blockIndex = 0

    for (let i = 0; i < words.length; i++) {
      const w = words[i]
      currentWords.push(w)

      const endsSentence = /[.?!]$/.test(w.punctuated_word.trim())
      const nextWord = words[i + 1]
      const hasPause = nextWord ? nextWord.start - w.end > 1.2 : false
      const isLongEnough = currentWords.length >= 14

      if (endsSentence || hasPause || isLongEnough || i === words.length - 1) {
        const start = currentWords[0].start
        const end = currentWords[currentWords.length - 1].end
        const rawText = currentWords.map((cw) => cw.punctuated_word).join(" ")
        blocks.push({
          id: `block_${blockIndex++}`,
          start,
          end,
          words: [...currentWords],
          rawText,
        })
        currentWords = []
      }
    }

    return blocks
  }, [words])

  // Identify currently spoken word index based on currentTime
  const currentSpokenIndex = useMemo(() => {
    return words.findIndex(
      (w) => currentTime >= w.start - 0.05 && currentTime <= w.end + 0.1
    )
  }, [words, currentTime])

  // Smooth auto-scroll to keep active word in view (paused during editing)
  useEffect(() => {
    if (editingBlockId !== null || inlineEditIdx !== null) return

    if (activeWordElemRef.current && documentContainerRef.current) {
      const container = documentContainerRef.current
      const element = activeWordElemRef.current
      const elementRect = element.getBoundingClientRect()
      const containerRect = container.getBoundingClientRect()

      if (
        elementRect.top < containerRect.top + 30 ||
        elementRect.bottom > containerRect.bottom - 30
      ) {
        element.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
        })
      }
    }
  }, [currentSpokenIndex, editingBlockId, inlineEditIdx])

  // Commit inline word edit on double-click
  const commitInlineWord = useCallback(
    (idx: number, newText: string) => {
      const text = newText.trim()
      if (text && words[idx] && text !== words[idx].punctuated_word) {
        const updated = [...words]
        updated[idx] = {
          ...updated[idx],
          punctuated_word: text,
          word: text.replace(/[.,!?]$/, "").toLowerCase(),
        }
        updateParentCaptions(updated)
      }
      setInlineEditIdx(null)
    },
    [words, updateParentCaptions]
  )

  // Start editing a full sentence block
  const handleStartEditBlock = (block: SentenceBlock) => {
    setEditingBlockId(block.id)
    setEditingBlockText(block.rawText)
    setInlineEditIdx(null)
  }

  // Save changes to a whole sentence block
  const handleSaveBlockEdit = (block: SentenceBlock) => {
    const trimmed = editingBlockText.trim()
    if (!trimmed) {
      toast.error("Sentence cannot be empty")
      return
    }

    const newWordTokens = trimmed.split(/\s+/)
    const origWords = block.words
    const blockStart = block.start
    const blockEnd = block.end
    const blockDuration = Math.max(0.2, blockEnd - blockStart)

    const updatedSentenceWords: CaptionWord[] = newWordTokens.map((token, i) => {
      const fractionStart = i / newWordTokens.length
      const fractionEnd = (i + 1) / newWordTokens.length
      const wordStart = Number((blockStart + fractionStart * blockDuration).toFixed(2))
      const wordEnd = Number((blockStart + fractionEnd * blockDuration).toFixed(2))

      return {
        word: token.replace(/[.,!?]$/, "").toLowerCase(),
        punctuated_word: token,
        start: wordStart,
        end: Math.max(wordStart + 0.05, wordEnd),
        confidence: 1.0,
        speaker: origWords[0]?.speaker || "0",
        layout: origWords[0]?.layout || (block as any).layout,
      }
    })

    const startIndexInAll = words.findIndex((w) => w.start >= block.start)
    if (startIndexInAll !== -1) {
      const newAllWords = [...words]
      newAllWords.splice(startIndexInAll, origWords.length, ...updatedSentenceWords)
      updateParentCaptions(newAllWords)
      toast.success("Sentence updated!")
    }

    setEditingBlockId(null)
    setEditingBlockText("")
  }

  // Find & Replace across all words
  const handleReplaceAll = () => {
    if (!searchQuery.trim()) {
      toast.error("Enter a search term")
      return
    }

    const queryLower = searchQuery.trim().toLowerCase()
    let count = 0

    const updated = words.map((w) => {
      const wClean = w.word.toLowerCase()
      if (wClean === queryLower || w.punctuated_word.toLowerCase().includes(queryLower)) {
        count++
        const isCapitalized =
          w.punctuated_word.length > 0 &&
          w.punctuated_word[0] === w.punctuated_word[0].toUpperCase()
        const punctuation = w.punctuated_word.match(/[.,!?]$/)?.[0] || ""
        let rep = replaceQuery.trim()
        if (isCapitalized && rep.length > 0) {
          rep = rep[0].toUpperCase() + rep.slice(1)
        }
        return {
          ...w,
          punctuated_word: rep + punctuation,
          word: rep.replace(/[.,!?]$/, "").toLowerCase(),
        }
      }
      return w
    })

    if (count === 0) {
      toast.info(`No matches found for “${searchQuery}”`)
      return
    }

    updateParentCaptions(updated)
    toast.success(`Replaced ${count} occurrence${count > 1 ? "s" : ""}`)
  }

  const totalWords = words.length
  return (
    <div className="flex h-full flex-col text-slate-800">
      {/* ── Document Top Bar: Search, Stats, Auto-scroll ── */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/80 bg-white px-4 py-2.5 text-xs shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 font-bold text-slate-800">
            <FileText className="size-4 text-indigo-600" />
            <span>Script &amp; Captions</span>
          </div>

          <span className="text-slate-300">|</span>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setShowSearch(!showSearch)}
            className={cn(
              "h-7 gap-1.5 px-2.5 font-semibold text-slate-600 transition-colors",
              showSearch ? "bg-indigo-50 text-indigo-700" : "hover:bg-slate-100"
            )}
          >
            <Search className="size-3.5" />
            <span>Find &amp; Replace</span>
          </Button>
        </div>
      </div>

      {/* ── Expandable Search & Replace Bar ── */}
      {showSearch && (
        <div className="flex flex-wrap items-center gap-2 border-b border-indigo-100 bg-indigo-50/50 p-2.5 shrink-0 animate-in fade-in-50 duration-150">
          <div className="relative flex-1 min-w-[130px]">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-slate-400" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search term…"
              autoComplete="off"
              className="h-8 pl-8 text-xs bg-white"
            />
          </div>

          <div className="relative flex-1 min-w-[130px]">
            <Replace className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-slate-400" />
            <Input
              value={replaceQuery}
              onChange={(e) => setReplaceQuery(e.target.value)}
              placeholder="Replace with…"
              autoComplete="off"
              className="h-8 pl-8 text-xs bg-white"
            />
          </div>

          <Button
            type="button"
            size="sm"
            onClick={handleReplaceAll}
            className="h-8 px-3 text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs"
          >
            Replace All
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setShowSearch(false)}
            className="h-8 px-2 text-slate-400 hover:text-slate-600"
          >
            <X className="size-3.5" />
          </Button>
        </div>
      )}

      {/* ── Main Document Script View ── */}
      <div
        ref={documentContainerRef}
        className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4 bg-white"
      >
        {sentenceBlocks.length === 0 ? (
          <div className="flex h-48 flex-col items-center justify-center gap-2 text-center text-slate-400">
            <Sparkles className="size-6 text-slate-300" />
            <p className="text-xs font-medium">No transcript available for this clip.</p>
          </div>
        ) : (
          sentenceBlocks.map((block) => {
            const isEditingThis = editingBlockId === block.id
            const isCurrentBlock =
              currentTime >= block.start - 0.1 && currentTime <= block.end + 0.1

            return (
              <div
                key={block.id}
                className={cn(
                  "group relative rounded-xl border transition-all duration-200 p-3 sm:p-3.5",
                  isCurrentBlock
                    ? "border-indigo-200 bg-indigo-50/20 shadow-xs"
                    : "border-transparent hover:border-slate-200 hover:bg-slate-50/60"
                )}
              >
                {/* Block Header Row: Timestamp + Play snippet button + Quick Edit */}
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        if (onPlaySnippet) {
                          onPlaySnippet(block.start, block.end)
                        } else {
                          onSeek(block.start)
                        }
                      }}
                      title="Play this sentence"
                      className="inline-flex items-center gap-1 rounded-md bg-slate-100 hover:bg-indigo-100 px-2 py-0.5 text-[11px] font-mono font-bold text-slate-600 hover:text-indigo-700 transition-colors"
                    >
                      <Play className="size-2.5 fill-current" />
                      <span>{formatTimecode(block.start)}</span>
                    </button>
                    <span className="text-[11px] text-slate-400 font-mono">
                      – {formatTimecode(block.end)}
                    </span>
                  </div>

                  {/* Actions on this block */}
                  {!isEditingThis && (
                    <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100 transition-opacity">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => handleStartEditBlock(block)}
                        className="h-6 px-2 text-[11px] font-semibold text-slate-600 hover:text-indigo-600 hover:bg-white gap-1 border border-slate-200/60 shadow-2xs"
                      >
                        <Edit3 className="size-3" />
                        <span>Edit Line</span>
                      </Button>
                    </div>
                  )}
                </div>

                {/* Block Content: Document Mode vs Editable Textarea Mode */}
                {isEditingThis ? (
                  <div className="space-y-2 animate-in fade-in-50 duration-150">
                    <textarea
                      value={editingBlockText}
                      onChange={(e) => setEditingBlockText(e.target.value)}
                      rows={2}
                      className="w-full rounded-lg border border-indigo-300 p-2 text-sm leading-relaxed font-normal text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white shadow-inner"
                      autoFocus
                    />
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setEditingBlockId(null)}
                        className="h-7 px-2.5 text-xs text-slate-500 hover:text-slate-800"
                      >
                        Cancel
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => handleSaveBlockEdit(block)}
                        className="h-7 px-3 text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs gap-1"
                      >
                        <Check className="size-3" />
                        <span>Save Line</span>
                      </Button>
                    </div>
                  </div>
                ) : (
                  /* Natural flowing paragraph text with clickable karaoke words */
                  <p className="text-sm leading-relaxed text-slate-700 select-text font-normal">
                    {block.words.map((cw, i) => {
                      const globalIdx = words.findIndex(
                        (w) => w.start === cw.start && w.word === cw.word
                      )
                      const isWordActive = globalIdx === currentSpokenIndex
                      const isWordEditing = inlineEditIdx === globalIdx

                      return (
                        <span
                          key={`${i}_${cw.start}`}
                          id={`word_span_${globalIdx}`}
                          ref={isWordActive ? activeWordElemRef : null}
                          contentEditable={isWordEditing}
                          suppressContentEditableWarning
                          onClick={(e) => {
                            if (isWordEditing) {
                              e.stopPropagation()
                              return
                            }
                            onSeek(cw.start)
                          }}
                          onDoubleClick={(e) => {
                            e.stopPropagation()
                            setInlineEditIdx(globalIdx)
                          }}
                          onBlur={(e) => {
                            if (isWordEditing) {
                              const newText = e.currentTarget.textContent || ""
                              commitInlineWord(globalIdx, newText)
                            }
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault()
                              e.currentTarget.blur()
                            } else if (e.key === "Escape") {
                              e.preventDefault()
                              if (words[globalIdx]) {
                                e.currentTarget.textContent = words[globalIdx].punctuated_word
                              }
                              setInlineEditIdx(null)
                            }
                          }}
                          title="Click to seek • Double-click to edit word inline"
                          className={cn(
                            "rounded px-0.5 py-0.5 transition-colors duration-150 mr-1 inline-block outline-none",
                            isWordEditing &&
                            "bg-indigo-100 text-indigo-950 font-semibold cursor-text ring-1 ring-indigo-400 select-text",
                            !isWordEditing &&
                            isWordActive &&
                            "bg-indigo-600 text-white font-semibold shadow-xs scale-105 select-none cursor-pointer",
                            !isWordEditing &&
                            !isWordActive &&
                            "hover:bg-slate-200/70 hover:text-slate-900 select-none cursor-pointer"
                          )}
                        >
                          {cw.punctuated_word}
                        </span>
                      )
                    })}
                  </p>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
