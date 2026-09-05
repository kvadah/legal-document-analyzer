'use client'

/**
 * Analysis view (`/documents/{id}`) — the primary review surface
 * (10-frontend-spec.md §4): document viewer pane + tabbed analysis pane,
 * wired to the Phase 2/3 pipelines.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import {
    AlertCircle,
    ArrowLeft,
    ChevronRight,
    FileWarning,
    Loader2,
    RefreshCw,
    ShieldAlert,
    Sparkles,
} from 'lucide-react'
import AppLayout from '@/app/app-layout'
import {
    ApiError,
    apiGetClauses,
    apiGetDocument,
    apiGetDocumentText,
    apiGetEntities,
    apiGetObligations,
    apiGetRisks,
    apiGetScore,
    apiGetSummary,
    apiPost,
    type ClauseListResponse,
    type DocumentOut,
    type DocumentTextResponse,
    type EntityListResponse,
    type ObligationListResponse,
    type RiskListResponse,
    type ScoreOut,
    type SummaryOut,
} from '@/lib/api-client'
import { ViewerJumpContext } from '@/components/analysis/CitationLink'
import DocumentViewer, { type JumpRequest } from '@/components/analysis/DocumentViewer'
import SummaryTab from '@/components/analysis/SummaryTab'
import ClausesTab from '@/components/analysis/ClausesTab'
import RisksTab from '@/components/analysis/RisksTab'
import ObligationsTab from '@/components/analysis/ObligationsTab'
import EntitiesTab from '@/components/analysis/EntitiesTab'
import { contractScoreTone } from '@/components/analysis/ScoreCards'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { EmptyState } from '@/components/ui/EmptyState'
import { docTypeMeta, formatBytes, statusMeta } from '@/lib/format'
import { formatConfidence } from '@/lib/analysis-meta'
import { cn } from '@/lib/cn'

interface AnalysisData {
    summary: SummaryOut
    clauses: ClauseListResponse
    risks: RiskListResponse
    obligations: ObligationListResponse
    entities: EntityListResponse
    score: ScoreOut
}

const TEXT_AVAILABLE_STATUSES = [
    'ingestion_ready',
    'ai_pipeline_processing',
    'analysis_ready',
]

const LOW_CONFIDENCE_THRESHOLD = 0.6

type TabKey = 'summary' | 'clauses' | 'risks' | 'obligations' | 'entities'

function PageSkeleton() {
    return (
        <div className="space-y-4">
            <div className="flex items-center gap-4">
                <div className="skeleton h-12 w-12 rounded-xl" />
                <div className="flex-1 space-y-2">
                    <div className="skeleton h-4 w-1/3" />
                    <div className="skeleton h-3 w-1/5" />
                </div>
                <div className="skeleton h-7 w-24 rounded-full" />
            </div>
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,480px)]">
                <div className="skeleton h-[600px] rounded-xl" />
                <div className="skeleton h-[600px] rounded-xl" />
            </div>
        </div>
    )
}

export default function AnalysisPage() {
    const params = useParams<{ id: string }>()
    const documentId = params.id

    const [doc, setDoc] = useState<DocumentOut | null>(null)
    const [docLoading, setDocLoading] = useState(true)
    const [docError, setDocError] = useState<ApiError | null>(null)

    const [text, setText] = useState<DocumentTextResponse | null>(null)
    const [textLoading, setTextLoading] = useState(false)

    const [analysis, setAnalysis] = useState<AnalysisData | null>(null)
    const [analysisLoading, setAnalysisLoading] = useState(false)
    const [analysisError, setAnalysisError] = useState<string | null>(null)

    const [activeTab, setActiveTab] = useState<TabKey>('summary')
    const [jumpRequest, setJumpRequest] = useState<JumpRequest | null>(null)
    const [retrying, setRetrying] = useState(false)
    const jumpCounter = useRef(0)

    const loadDocument = useCallback(
        async (silent = false) => {
            if (!silent) setDocLoading(true)
            try {
                const d = await apiGetDocument(documentId)
                setDoc(d)
                setDocError(null)
            } catch (err) {
                setDocError(
                    err instanceof ApiError
                        ? err
                        : new ApiError('Failed to load document'),
                )
            } finally {
                setDocLoading(false)
            }
        },
        [documentId],
    )

    useEffect(() => {
        void loadDocument()
    }, [loadDocument])

    const busy =
        doc != null && doc.status !== 'analysis_ready' && doc.status !== 'error'

    // Poll while the document is still moving through the pipeline
    useEffect(() => {
        if (!doc || !busy) return
        const id = setInterval(() => void loadDocument(true), 4000)
        return () => clearInterval(id)
    }, [doc, busy, loadDocument])

    // Load viewer text + analysis outputs as soon as the document allows it
    useEffect(() => {
        if (!doc) return
        if (TEXT_AVAILABLE_STATUSES.includes(doc.status)) {
            setTextLoading(true)
            apiGetDocumentText(documentId)
                .then(setText)
                .catch(() => setText(null))
                .finally(() => setTextLoading(false))
        }
        if (doc.status === 'analysis_ready' && !analysis && !analysisLoading) {
            setAnalysisLoading(true)
            setAnalysisError(null)
            Promise.all([
                apiGetSummary(documentId),
                apiGetClauses(documentId),
                apiGetRisks(documentId),
                apiGetObligations(documentId),
                apiGetEntities(documentId),
                apiGetScore(documentId),
            ])
                .then(
                    ([summary, clauses, risks, obligations, entities, score]) => {
                        setAnalysis({
                            summary,
                            clauses,
                            risks,
                            obligations,
                            entities,
                            score,
                        })
                    },
                )
                .catch(err => {
                    setAnalysisError(
                        err instanceof Error
                            ? err.message
                            : 'Failed to load analysis',
                    )
                })
                .finally(() => setAnalysisLoading(false))
        }
    }, [doc, documentId, analysis, analysisLoading])

    const requestJump = useCallback(
        (pageNumber: number, highlightText?: string | null) => {
            jumpCounter.current += 1
            setJumpRequest({
                page: pageNumber,
                highlightText: highlightText ?? null,
                nonce: jumpCounter.current,
            })
        },
        [],
    )

    const retry = useCallback(async () => {
        setRetrying(true)
        try {
            await apiPost(`/documents/${documentId}/retry`, {})
            await loadDocument(true)
        } catch {
            // next poll/manual refresh will surface the state
        } finally {
            setRetrying(false)
        }
    }, [documentId, loadDocument])

    const tabs = useMemo(
        () => [
            { key: 'summary' as TabKey, label: 'Summary' },
            {
                key: 'clauses' as TabKey,
                label: 'Clauses',
                count: analysis?.clauses.total,
            },
            {
                key: 'risks' as TabKey,
                label: 'Risks',
                count: analysis?.risks.total,
            },
            {
                key: 'obligations' as TabKey,
                label: 'Obligations',
                count: analysis?.obligations.total,
            },
            {
                key: 'entities' as TabKey,
                label: 'Entities',
                count: analysis?.entities.total,
            },
        ],
        [analysis],
    )

    const lowConfidence =
        analysis?.score.ai_confidence_score != null &&
        analysis.score.ai_confidence_score < LOW_CONFIDENCE_THRESHOLD

    // ── Render ───────────────────────────────────────────────────────────────

    if (docLoading) {
        return (
            <AppLayout>
                <div className="mx-auto max-w-[1600px]">
                    <PageSkeleton />
                </div>
            </AppLayout>
        )
    }

    if (docError?.code === 'not_found') {
        return (
            <AppLayout>
                <div className="mx-auto max-w-3xl">
                    <EmptyState
                        icon={FileWarning}
                        title="Document not found"
                        description="This document doesn't exist, is still processing, or belongs to another organisation."
                        action={
                            <Link
                                href="/contracts"
                                className="btn-primary px-6 py-3"
                            >
                                <ArrowLeft size={16} />
                                Back to Contracts
                            </Link>
                        }
                    />
                </div>
            </AppLayout>
        )
    }

    if (docError || !doc) {
        return (
            <AppLayout>
                <div className="mx-auto max-w-3xl space-y-4">
                    <div className="card flex items-center gap-3 p-6 text-[14px] text-ink-600">
                        <AlertCircle size={18} className="shrink-0 text-rose-400" />
                        {docError?.message ?? 'Failed to load document'}
                        <button
                            onClick={() => void loadDocument()}
                            className="btn-secondary ml-auto px-3.5 py-2"
                        >
                            <RefreshCw size={14} />
                            Retry
                        </button>
                    </div>
                </div>
            </AppLayout>
        )
    }

    const type = docTypeMeta(doc.document_type)
    const status = statusMeta(doc.status)
    const scoreTone = contractScoreTone(analysis?.score.contract_score)

    return (
        <AppLayout>
            <ViewerJumpContext.Provider value={requestJump}>
                <div className="mx-auto max-w-[1600px] space-y-4">
                    {/* Header */}
                    <header className="flex flex-wrap items-center gap-x-4 gap-y-3 animate-fade-up">
                        <Link
                            href="/contracts"
                            className="btn-ghost h-9 w-9 shrink-0 rounded-xl border border-ink-100 p-0"
                            aria-label="Back to contracts"
                        >
                            <ArrowLeft size={16} />
                        </Link>
                        <span
                            className={cn(
                                'flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-[10px] font-bold ring-1 ring-inset',
                                type.tile,
                            )}
                        >
                            {type.glyph}
                        </span>
                        <div className="min-w-0 flex-1">
                            <h1 className="truncate font-display text-[22px] font-semibold leading-tight tracking-tight text-ink-900">
                                {doc.filename}
                            </h1>
                            <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12.5px] text-ink-400">
                                <span>{type.label}</span>
                                <span aria-hidden>·</span>
                                <span>{formatBytes(doc.file_size_bytes)}</span>
                                {doc.page_count != null && (
                                    <>
                                        <span aria-hidden>·</span>
                                        <span>{doc.page_count} pages</span>
                                    </>
                                )}
                                <span aria-hidden>·</span>
                                <StatusBadge status={doc.status} />
                            </p>
                        </div>

                        {analysis && (
                            <div className="flex items-center gap-2">
                                <button
                                    type="button"
                                    onClick={() => setActiveTab('summary')}
                                    className={cn(
                                        'pill cursor-default px-3 py-1 text-[12px]',
                                        'bg-white text-ink-600 ring-1 ring-inset ring-ink-200 transition-colors hover:ring-ink-300',
                                    )}
                                    title="Contract score — click for breakdown"
                                >
                                    Score
                                    <span
                                        className={cn(
                                            'font-display text-[14px] font-bold',
                                            scoreTone.text,
                                        )}
                                    >
                                        {analysis.score.contract_score ?? '—'}
                                    </span>
                                </button>
                                <span className="pill cursor-default bg-white px-3 py-1 text-[12px] text-ink-600 ring-1 ring-inset ring-ink-200">
                                    AI conf.
                                    <span className="font-semibold">
                                        {formatConfidence(
                                            analysis.score.ai_confidence_score,
                                        )}
                                    </span>
                                </span>
                            </div>
                        )}
                    </header>

                    {/* Pipeline error */}
                    {doc.status === 'error' && (
                        <div className="card flex flex-wrap items-center gap-3 border-rose-200/70 p-5">
                            <FileWarning
                                size={20}
                                className="shrink-0 text-rose-500"
                            />
                            <div className="min-w-0 flex-1">
                                <p className="text-[14px] font-semibold text-ink-900">
                                    Processing failed
                                </p>
                                <p className="mt-0.5 text-[13px] text-ink-500">
                                    {doc.status_detail ??
                                        'The pipeline hit an error while processing this document.'}
                                </p>
                            </div>
                            <button
                                onClick={() => void retry()}
                                disabled={retrying}
                                className="btn-primary px-4 py-2.5"
                            >
                                <RefreshCw
                                    size={15}
                                    className={cn(retrying && 'animate-spin')}
                                />
                                Retry processing
                            </button>
                        </div>
                    )}

                    {/* Still processing */}
                    {busy && (
                        <div className="card relative overflow-hidden p-10">
                            <div className="bg-grid mask-fade-b pointer-events-none absolute inset-0 opacity-50" />
                            <div className="relative mx-auto flex max-w-md flex-col items-center text-center">
                                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-b from-indigo-500 to-violet-600 text-white shadow-glow">
                                    <Loader2
                                        size={26}
                                        className="animate-spin"
                                    />
                                </div>
                                <h2 className="mt-5 font-display text-xl font-semibold text-ink-900">
                                    {status.label}…
                                </h2>
                                <p className="mt-2 text-[13.5px] leading-relaxed text-ink-500">
                                    This document is still moving through the
                                    pipeline. This page updates automatically —
                                    no need to refresh.
                                </p>
                                {doc.status_detail && (
                                    <p className="mt-2 text-[12.5px] text-ink-400">
                                        {doc.status_detail}
                                    </p>
                                )}
                                <div className="mt-5 flex items-center gap-1.5">
                                    {[0, 1, 2].map(i => (
                                        <span
                                            key={i}
                                            className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400"
                                            style={{
                                                animationDelay: `${i * 150}ms`,
                                            }}
                                        />
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Analysis view */}
                    {!busy && doc.status === 'analysis_ready' && (
                        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,500px)]">
                            {/* Viewer pane */}
                            <div className="xl:sticky xl:top-6 xl:h-[calc(100vh-170px)]">
                                <DocumentViewer
                                    text={text}
                                    filename={doc.filename}
                                    jumpRequest={jumpRequest}
                                    loading={textLoading}
                                />
                            </div>

                            {/* Analysis pane */}
                            <div className="flex min-w-0 flex-col gap-3 xl:h-[calc(100vh-170px)]">
                                {lowConfidence && (
                                    <div
                                        className="flex items-start gap-2.5 rounded-xl border border-rose-200/80 bg-rose-50 px-4 py-3 text-[13px] leading-relaxed text-rose-700 animate-scale-in"
                                        role="status"
                                    >
                                        <ShieldAlert
                                            size={15}
                                            className="mt-0.5 shrink-0"
                                        />
                                        <span>
                                            <span className="font-semibold">
                                                Low AI confidence (
                                                {formatConfidence(
                                                    analysis?.score
                                                        .ai_confidence_score,
                                                )}
                                                )
                                            </span>{' '}
                                            — treat these results as a first
                                            pass and verify findings manually.
                                        </span>
                                    </div>
                                )}

                                {analysisError && (
                                    <div className="flex items-center gap-3 rounded-xl border border-rose-200/80 bg-rose-50 px-4 py-3 text-[13px] text-rose-700">
                                        <AlertCircle
                                            size={15}
                                            className="shrink-0"
                                        />
                                        {analysisError}
                                        <button
                                            onClick={() => setAnalysis(null)}
                                            className="ml-auto font-semibold underline-offset-2 hover:underline"
                                        >
                                            Retry
                                        </button>
                                    </div>
                                )}

                                <div className="card flex min-h-[560px] flex-1 flex-col overflow-hidden">
                                    {/* Tab bar */}
                                    <nav
                                        className="flex gap-1 overflow-x-auto border-b border-ink-100 bg-ink-50/50 px-2.5 py-2"
                                        aria-label="Analysis sections"
                                    >
                                        {tabs.map(tab => {
                                            const isActive =
                                                activeTab === tab.key
                                            return (
                                                <button
                                                    key={tab.key}
                                                    type="button"
                                                    onClick={() =>
                                                        setActiveTab(tab.key)
                                                    }
                                                    aria-current={isActive}
                                                    className={cn(
                                                        'flex shrink-0 items-center gap-1.5 rounded-lg px-3.5 py-2 text-[13px] font-semibold transition-all duration-200',
                                                        isActive
                                                            ? 'bg-white text-indigo-700 shadow-soft ring-1 ring-ink-100'
                                                            : 'text-ink-400 hover:bg-white/60 hover:text-ink-600',
                                                    )}
                                                >
                                                    {tab.label}
                                                    {tab.count != null && (
                                                        <span
                                                            className={cn(
                                                                'rounded-full px-1.5 py-px text-[10.5px] font-bold',
                                                                isActive
                                                                    ? 'bg-indigo-50 text-indigo-600'
                                                                    : 'bg-ink-100 text-ink-400',
                                                            )}
                                                        >
                                                            {tab.count}
                                                        </span>
                                                    )}
                                                </button>
                                            )
                                        })}
                                    </nav>

                                    {/* Tab content */}
                                    <div className="flex-1 overflow-y-auto p-4">
                                        {analysisLoading && (
                                            <div className="space-y-3">
                                                {[0, 1, 2].map(i => (
                                                    <div
                                                        key={i}
                                                        className="skeleton h-24 rounded-xl"
                                                    />
                                                ))}
                                            </div>
                                        )}
                                        {!analysisLoading && analysis && (
                                            <>
                                                {activeTab === 'summary' && (
                                                    <SummaryTab
                                                        summary={analysis.summary}
                                                        risks={analysis.risks.items}
                                                        score={analysis.score}
                                                    />
                                                )}
                                                {activeTab === 'clauses' && (
                                                    <ClausesTab
                                                        clauses={analysis.clauses}
                                                    />
                                                )}
                                                {activeTab === 'risks' && (
                                                    <RisksTab
                                                        risks={analysis.risks}
                                                        document={doc}
                                                    />
                                                )}
                                                {activeTab ===
                                                    'obligations' && (
                                                    <ObligationsTab
                                                        obligations={
                                                            analysis.obligations
                                                        }
                                                    />
                                                )}
                                                {activeTab === 'entities' && (
                                                    <EntitiesTab
                                                        entities={
                                                            analysis.entities
                                                        }
                                                    />
                                                )}
                                            </>
                                        )}
                                        {!analysisLoading && !analysis && !analysisError && (
                                            <div className="flex h-full flex-col items-center justify-center gap-3 py-16 text-center">
                                                <Sparkles
                                                    size={22}
                                                    className="text-indigo-300"
                                                />
                                                <p className="text-[13.5px] text-ink-400">
                                                    Analysis results will appear
                                                    here.
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Inline AI disclaimer (layout-level one is
                                    always visible too — 11-security §8) */}
                                <p className="flex items-center justify-center gap-1.5 px-2 text-center text-[11px] text-gold-800">
                                    <ShieldAlert
                                        size={11}
                                        className="shrink-0 text-gold-600"
                                    />
                                    AI-generated analysis — not legal advice.
                                </p>
                            </div>
                        </div>
                    )}

                    {/* Ingested but AI not finished — offer text-only preview */}
                    {!busy && doc.status === 'ingestion_ready' && (
                        <div className="card flex flex-wrap items-center gap-3 p-5">
                            <ChevronRight
                                size={16}
                                className="shrink-0 text-indigo-400"
                            />
                            <p className="min-w-0 flex-1 text-[13.5px] text-ink-600">
                                Ingestion complete — AI analysis hasn&apos;t run
                                yet for this document.
                            </p>
                            <button
                                onClick={() => void retry()}
                                disabled={retrying}
                                className="btn-secondary px-4 py-2"
                            >
                                <RefreshCw
                                    size={14}
                                    className={cn(retrying && 'animate-spin')}
                                />
                                Queue analysis
                            </button>
                        </div>
                    )}
                </div>
            </ViewerJumpContext.Provider>
        </AppLayout>
    )
}
