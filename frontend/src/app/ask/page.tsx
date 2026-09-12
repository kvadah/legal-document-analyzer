'use client'

/**
 * Cross-document Q&A (`/ask`) — grounded RAG chat across the org corpus
 * or a selected subset of documents (08 §3, 10-frontend-spec.md).
 * Citations carry per-document attribution and deep-link into the
 * Analysis viewer at the cited page.
 */
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import {
    BookOpenCheck,
    FileWarning,
    Library,
    Loader2,
    MessageCircleQuestion,
    SendHorizontal,
    ShieldAlert,
    UserRound,
} from 'lucide-react'
import AppLayout from '@/app/app-layout'
import {
    apiAskAllDocumentsStream,
    apiListDocuments,
    type AskCitation,
    type DocumentOut,
} from '@/lib/api-client'
import { PageHeader } from '@/components/ui/PageHeader'
import { DocumentMultiSelect } from '@/components/ui/DocumentPicker'
import { cn } from '@/lib/cn'

const SEARCHABLE_STATUSES = ['ingestion_ready', 'ai_pipeline_processing', 'analysis_ready']

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
    getHref,
}: {
    text: string
    citations: Citation[]
    getHref: (citation: Citation) => string
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
                    <Link
                        key={i}
                        href={getHref(citation)}
                        title={citation.quote}
                        className="mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded bg-indigo-100 px-1 align-middle text-[10.5px] font-bold text-indigo-700 transition-colors hover:bg-indigo-200"
                    >
                        {citation.index}
                    </Link>
                )
            })}
        </>
    )
}

function citationHref(citation: Citation): string {
    return `/documents/${citation.document_id}?page=${citation.page_number}`
}

function AskView() {
    const searchParams = useSearchParams()
    const initialQuestion = searchParams.get('q')

    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [input, setInput] = useState('')
    const [busy, setBusy] = useState(false)
    const conversationRef = useRef<string | null>(null)
    const scrollRef = useRef<HTMLDivElement>(null)
    const initialAsked = useRef(false)

    const [documents, setDocuments] = useState<DocumentOut[] | null>(null)
    const [scopeIds, setScopeIds] = useState<string[]>([])

    const searchable = useMemo(
        () => (documents ?? []).filter(d => SEARCHABLE_STATUSES.includes(d.status)),
        [documents],
    )

    useEffect(() => {
        let cancelled = false
        apiListDocuments()
            .then(res => {
                if (!cancelled) setDocuments(res.items)
            })
            .catch(() => {
                if (!cancelled) setDocuments([])
            })
        return () => {
            cancelled = true
        }
    }, [])

    const toggleScope = useCallback((id: string) => {
        setScopeIds(prev =>
            prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id],
        )
    }, [])

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

            const updateAssistant = (updater: (msg: ChatMessage) => ChatMessage) => {
                setMessages(prev =>
                    prev.map((m, i) =>
                        i === prev.length - 1 && m.role === 'assistant' ? updater(m) : m,
                    ),
                )
            }

            await apiAskAllDocumentsStream(
                trimmed,
                conversationRef.current,
                {
                    onCitations: citations => updateAssistant(m => ({ ...m, citations })),
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
                },
                scopeIds.length ? { document_ids: scopeIds } : null,
            )
            setBusy(false)
        },
        [busy, scopeIds, scrollToBottom],
    )

    // Prefilled question from the Search page's cross-document "Ask" link
    useEffect(() => {
        if (initialQuestion && !initialAsked.current) {
            initialAsked.current = true
            void ask(initialQuestion)
        }
    }, [initialQuestion, ask])

    return (
        <AppLayout>
            <div className="mx-auto flex h-[calc(100vh-150px)] max-w-3xl flex-col gap-4">
                <PageHeader
                    eyebrow="Ask"
                    title="Cross-document Q&A"
                    description="Ask a question across your whole document library — answers are grounded with citations attributed to the right source document."
                />

                {/* Scope selector */}
                <div className="card flex flex-wrap items-center gap-3 px-4 py-3">
                    <span className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-[0.12em] text-ink-500">
                        <Library size={13} className="text-indigo-400" />
                        Scope
                    </span>
                    <div className="min-w-[220px] flex-1">
                        <DocumentMultiSelect
                            documents={searchable}
                            selectedIds={scopeIds}
                            onToggle={toggleScope}
                        />
                    </div>
                    <span className="text-[12px] text-ink-400">
                        {searchable.length} searchable document
                        {searchable.length === 1 ? '' : 's'}
                    </span>
                </div>

                {/* Chat */}
                <div className="card flex min-h-0 flex-1 flex-col overflow-hidden">
                    <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-5">
                        {messages.length === 0 && (
                            <div className="flex flex-col items-center gap-3 py-10 text-center">
                                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-b from-indigo-500 to-violet-600 text-white shadow-glow">
                                    <MessageCircleQuestion size={22} />
                                </div>
                                <div>
                                    <p className="font-display text-[17px] font-semibold text-ink-900">
                                        Ask your documents anything
                                    </p>
                                    <p className="mx-auto mt-1.5 max-w-md text-[13px] leading-relaxed text-ink-500">
                                        Answers draw only on your corpus, with each point
                                        attributed to the document it came from.
                                        I&apos;ll say so when nothing covers your question.
                                    </p>
                                </div>
                                <div className="mt-1 flex flex-wrap justify-center gap-2">
                                    {[
                                        'What are the payment fees across my contracts?',
                                        'Which agreements mention Acme Corp?',
                                        'What notice periods apply before termination?',
                                    ].map(suggestion => (
                                        <button
                                            key={suggestion}
                                            type="button"
                                            onClick={() => void ask(suggestion)}
                                            disabled={busy}
                                            className="rounded-full border border-ink-100 bg-white px-3.5 py-1.5 text-[12px] font-medium text-ink-600 transition-colors hover:border-indigo-200 hover:bg-indigo-50/50 hover:text-indigo-700 disabled:opacity-50"
                                        >
                                            {suggestion}
                                        </button>
                                    ))}
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
                                            Searching your documents…
                                        </span>
                                    ) : (
                                        <div className="space-y-2.5">
                                            {message.notFound && (
                                                <p className="flex items-center gap-1.5 text-[12px] font-semibold text-amber-600">
                                                    <FileWarning size={12.5} />
                                                    Not found in your documents
                                                </p>
                                            )}
                                            <p className="whitespace-pre-wrap">
                                                <AnswerText
                                                    text={message.text}
                                                    citations={message.citations}
                                                    getHref={citationHref}
                                                />
                                                {message.streaming && message.text && (
                                                    <span className="ml-0.5 inline-block h-3.5 w-[2px] animate-pulse bg-indigo-400 align-middle" />
                                                )}
                                            </p>
                                            {message.citations.length > 0 && (
                                                <div className="flex flex-col gap-1.5 border-t border-ink-100 pt-2">
                                                    {message.citations.map(citation => (
                                                        <Link
                                                            key={citation.chunk_id}
                                                            href={citationHref(citation)}
                                                            title={citation.quote}
                                                            className="flex items-start gap-2 rounded-md bg-white px-2 py-1 text-[11px] font-medium text-ink-500 ring-1 ring-inset ring-ink-100 transition-colors hover:text-indigo-700 hover:ring-indigo-200"
                                                        >
                                                            <FileWarning
                                                                size={11}
                                                                className="mt-0.5 shrink-0 text-ink-300"
                                                            />
                                                            <span className="min-w-0">
                                                                <span className="block max-w-[320px] truncate font-semibold text-ink-600">
                                                                    {citation.document_name ?? 'Document'}
                                                                </span>
                                                                <span className="block max-w-[320px] truncate">
                                                                    “{citation.quote}” ·
                                                                    p.{citation.page_number}
                                                                </span>
                                                            </span>
                                                        </Link>
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
                        className="flex items-end gap-2 border-t border-ink-100 p-4"
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
                            placeholder="Ask across all documents…"
                            disabled={busy}
                            aria-label="Ask a question across your documents"
                            className="field max-h-28 min-h-[42px] flex-1 resize-none py-2.5 text-[13.5px]"
                        />
                        <button
                            type="submit"
                            disabled={busy || !input.trim()}
                            aria-label="Send question"
                            className="btn-primary h-[42px] w-[42px] shrink-0 p-0"
                        >
                            {busy ? (
                                <Loader2 size={16} className="animate-spin" />
                            ) : (
                                <SendHorizontal size={16} />
                            )}
                        </button>
                    </form>
                </div>

                <p className="flex items-center justify-center gap-1.5 text-center text-[10.5px] text-gold-800">
                    <ShieldAlert size={10.5} className="shrink-0 text-gold-600" />
                    AI-generated answers — not legal advice.
                </p>
            </div>
        </AppLayout>
    )
}

export default function AskPage() {
    // useSearchParams requires a Suspense boundary during prerendering
    return (
        <Suspense fallback={null}>
            <AskView />
        </Suspense>
    )
}
