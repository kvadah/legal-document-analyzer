'use client'

/**
 * Q&A tab — chat-style grounded RAG interface scoped to one document
 * (10-frontend-spec.md §4). Answers stream over SSE with inline citation
 * markers rendered as clickable references that jump the document viewer.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
    BookOpenCheck,
    FileWarning,
    Loader2,
    MessageCircleQuestion,
    SendHorizontal,
    ShieldAlert,
    UserRound,
} from 'lucide-react'
import {
    apiAskStream,
    type AskCitation,
} from '@/lib/api-client'
import { useViewerJump } from '@/components/analysis/CitationLink'
import { cn } from '@/lib/cn'

type Citation = AskCitation

interface ChatMessage {
    role: 'user' | 'assistant'
    text: string
    citations: Citation[]
    streaming?: boolean
    notFound?: boolean
}

function AnswerText({
    text,
    citations,
    onCitationClick,
}: {
    text: string
    citations: Citation[]
    onCitationClick: (citation: Citation) => void
}) {
    const byIndex = new Map(citations.map(c => [c.index, c]))
    const parts = text.split(/(\[\d+\])/g)
    return (
        <>
            {parts.map((part, i) => {
                const match = part.match(/^\[(\d+)\]$/)
                if (!match) return <span key={i}>{part}</span>
                const citation = byIndex.get(Number(match[1]))
                if (!citation) return null
                return (
                    <button
                        key={i}
                        type="button"
                        onClick={() => onCitationClick(citation)}
                        title={citation.quote}
                        className="mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded bg-indigo-100 px-1 align-middle text-[10.5px] font-bold text-indigo-700 transition-colors hover:bg-indigo-200"
                    >
                        {citation.index}
                    </button>
                )
            })}
        </>
    )
}

export default function QaTab({
    documentId,
    initialQuestion,
}: {
    documentId: string
    initialQuestion?: string | null
}) {
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [input, setInput] = useState('')
    const [busy, setBusy] = useState(false)
    const conversationRef = useRef<string | null>(null)
    const scrollRef = useRef<HTMLDivElement>(null)
    const jump = useViewerJump()
    const initialAsked = useRef(false)

    const scrollToBottom = useCallback(() => {
        requestAnimationFrame(() => {
            scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
        })
    }, [])

    const ask = useCallback(
        async (question: string) => {
            const trimmed = question.trim()
            if (!trimmed || busy) return
            setBusy(true)
            setInput('')
            setMessages(prev => [
                ...prev,
                { role: 'user', text: trimmed, citations: [] },
                { role: 'assistant', text: '', citations: [], streaming: true },
            ])
            scrollToBottom()

            const updateAssistant = (
                updater: (msg: ChatMessage) => ChatMessage,
            ) => {
                setMessages(prev =>
                    prev.map((m, i) =>
                        i === prev.length - 1 && m.role === 'assistant' ? updater(m) : m,
                    ),
                )
            }

            await apiAskStream(documentId, trimmed, conversationRef.current, {
                onCitations: citations =>
                    updateAssistant(m => ({ ...m, citations })),
                onDelta: text => {
                    updateAssistant(m => ({ ...m, text: m.text + text }))
                    scrollToBottom()
                },
                onDone: result => {
                    conversationRef.current = result.conversation_id
                    updateAssistant(m => ({
                        ...m,
                        text: m.text || result.answer,
                        streaming: false,
                        notFound: !result.found_in_document,
                    }))
                    scrollToBottom()
                },
                onError: message => {
                    updateAssistant(m => ({
                        ...m,
                        text: m.text || `Sorry — ${message}`,
                        streaming: false,
                    }))
                },
            })
            setBusy(false)
        },
        [busy, documentId, scrollToBottom],
    )

    // Prefilled question from the Search page's "Ask" route
    useEffect(() => {
        if (initialQuestion && !initialAsked.current) {
            initialAsked.current = true
            void ask(initialQuestion)
        }
    }, [initialQuestion, ask])

    const handleCitationClick = useCallback(
        (citation: Citation) => {
            jump?.(citation.page_number, citation.quote)
        },
        [jump],
    )

    return (
        <div className="flex h-full min-h-[480px] flex-col">
            {/* Messages */}
            <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto pr-1">
                {messages.length === 0 && (
                    <div className="flex flex-col items-center gap-3 py-12 text-center">
                        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-b from-indigo-500 to-violet-600 text-white shadow-glow">
                            <MessageCircleQuestion size={22} />
                        </div>
                        <div>
                            <p className="font-display text-[17px] font-semibold text-ink-900">
                                Ask this document anything
                            </p>
                            <p className="mx-auto mt-1.5 max-w-sm text-[13px] leading-relaxed text-ink-500">
                                Answers are grounded in the document text with clickable
                                citations. I&apos;ll say so when the document doesn&apos;t
                                cover something.
                            </p>
                        </div>
                        <div className="mt-1 flex flex-wrap justify-center gap-2">
                            {['What are the payment terms?', 'How can this agreement end?', 'Who are the parties?'].map(
                                suggestion => (
                                    <button
                                        key={suggestion}
                                        type="button"
                                        onClick={() => void ask(suggestion)}
                                        disabled={busy}
                                        className="rounded-full border border-ink-100 bg-white px-3.5 py-1.5 text-[12px] font-medium text-ink-600 transition-colors hover:border-indigo-200 hover:bg-indigo-50/50 hover:text-indigo-700 disabled:opacity-50"
                                    >
                                        {suggestion}
                                    </button>
                                ),
                            )}
                        </div>
                    </div>
                )}

                {messages.map((message, i) => (
                    <div
                        key={i}
                        className={cn(
                            'animate-fade-up flex gap-2.5',
                            message.role === 'user' && 'justify-end',
                        )}
                    >
                        {message.role === 'assistant' && (
                            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-b from-indigo-500 to-violet-600 text-white">
                                <BookOpenCheck size={13} />
                            </span>
                        )}
                        <div
                            className={cn(
                                'max-w-[85%] rounded-xl px-3.5 py-2.5 text-[13px] leading-relaxed',
                                message.role === 'user'
                                    ? 'bg-indigo-600 text-white'
                                    : 'bg-ink-50 text-ink-800',
                            )}
                        >
                            {message.role === 'user' ? (
                                message.text
                            ) : message.streaming && !message.text ? (
                                <span className="flex items-center gap-2 text-ink-400">
                                    <Loader2 size={13} className="animate-spin" />
                                    Searching the document…
                                </span>
                            ) : (
                                <div className="space-y-2.5">
                                    {message.notFound && (
                                        <p className="flex items-center gap-1.5 text-[12px] font-semibold text-amber-600">
                                            <FileWarning size={12.5} />
                                            Not found in this document
                                        </p>
                                    )}
                                    <p className="whitespace-pre-wrap">
                                        <AnswerText
                                            text={message.text}
                                            citations={message.citations}
                                            onCitationClick={handleCitationClick}
                                        />
                                        {message.streaming && message.text && (
                                            <span className="ml-0.5 inline-block h-3.5 w-[2px] animate-pulse bg-indigo-400 align-middle" />
                                        )}
                                    </p>
                                    {message.citations.length > 0 && (
                                        <div className="flex flex-wrap gap-1.5 border-t border-ink-100 pt-2">
                                            {message.citations.map(citation => (
                                                <button
                                                    key={citation.chunk_id}
                                                    type="button"
                                                    onClick={() => handleCitationClick(citation)}
                                                    title={citation.quote}
                                                    className="max-w-[240px] truncate rounded-md bg-white px-2 py-1 text-[11px] font-medium text-ink-500 ring-1 ring-inset ring-ink-100 transition-colors hover:text-indigo-700 hover:ring-indigo-200"
                                                >
                                                    “{citation.quote}” · p.{citation.page_number}
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                        {message.role === 'user' && (
                            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-ink-200 text-ink-600">
                                <UserRound size={13} />
                            </span>
                        )}
                    </div>
                ))}
            </div>

            {/* Input */}
            <form
                onSubmit={e => {
                    e.preventDefault()
                    void ask(input)
                }}
                className="mt-3 flex items-end gap-2 border-t border-ink-100 pt-3"
            >
                <textarea
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={e => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault()
                            void ask(input)
                        }
                    }}
                    rows={1}
                    placeholder="Ask about this document…"
                    disabled={busy}
                    aria-label="Ask a question about this document"
                    className="field max-h-28 min-h-[42px] flex-1 resize-none py-2.5 text-[13.5px]"
                />
                <button
                    type="submit"
                    disabled={busy || !input.trim()}
                    aria-label="Send question"
                    className="btn-primary h-[42px] w-[42px] shrink-0 p-0"
                >
                    {busy ? <Loader2 size={16} className="animate-spin" /> : <SendHorizontal size={16} />}
                </button>
            </form>

            <p className="mt-2 flex items-center justify-center gap-1.5 text-center text-[10.5px] text-gold-800">
                <ShieldAlert size={10.5} className="shrink-0 text-gold-600" />
                AI-generated answers — not legal advice.
            </p>
        </div>
    )
}
