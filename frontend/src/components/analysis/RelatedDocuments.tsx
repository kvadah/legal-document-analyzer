'use client'

/**
 * Related Documents panel (08 §2) — linked documents with relationship type
 * and quick navigation, plus system-inferred suggestions that require
 * confirmation, and manual linking for reviewer/admin users.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
    AlertCircle,
    ArrowRight,
    Check,
    FileText,
    Link2,
    Loader2,
    Plus,
    Sparkles,
    Trash2,
    X,
} from 'lucide-react'
import {
    apiConfirmRelationship,
    apiCreateRelationship,
    apiDeleteRelationship,
    apiListDocuments,
    apiListRelationships,
    type DocumentOut,
    type RelatedDocument,
    type RelationshipType,
} from '@/lib/api-client'
import { useAuth } from '@/context/AuthContext'
import { DocumentSelect } from '@/components/ui/DocumentPicker'
import { docTypeMeta } from '@/lib/format'
import { cn } from '@/lib/cn'

const RELATIONSHIP_LABELS: Record<RelationshipType, string> = {
    amendment: 'Amendment of',
    exhibit: 'Exhibit to',
    related_agreement: 'Related to',
    supersedes: 'Supersedes',
}

const RELATIONSHIP_TYPES: RelationshipType[] = [
    'amendment',
    'exhibit',
    'related_agreement',
    'supersedes',
]

export default function RelatedDocuments({ documentId }: { documentId: string }) {
    const { user } = useAuth()
    const canEdit = user?.role === 'admin' || user?.role === 'reviewer'

    const [relationships, setRelationships] = useState<RelatedDocument[] | null>(null)
    const [error, setError] = useState<string | null>(null)

    const [adding, setAdding] = useState(false)
    const [documents, setDocuments] = useState<DocumentOut[]>([])
    const [linkTarget, setLinkTarget] = useState<string | null>(null)
    const [linkType, setLinkType] = useState<RelationshipType>('related_agreement')
    const [actionBusy, setActionBusy] = useState<string | null>(null)

    const load = useCallback(async () => {
        try {
            const res = await apiListRelationships(documentId)
            setRelationships(res.relationships)
            setError(null)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load links')
        }
    }, [documentId])

    useEffect(() => {
        void load()
    }, [load])

    useEffect(() => {
        if (!adding || documents.length > 0) return
        apiListDocuments()
            .then(res =>
                setDocuments(res.items.filter(d => d.id !== documentId)),
            )
            .catch(() => setDocuments([]))
    }, [adding, documents.length, documentId])

    const confirmed = useMemo(
        () => (relationships ?? []).filter(r => !r.suggested),
        [relationships],
    )
    const suggestions = useMemo(
        () => (relationships ?? []).filter(r => r.suggested),
        [relationships],
    )

    const runAction = useCallback(
        async (key: string, action: () => Promise<unknown>) => {
            setActionBusy(key)
            try {
                await action()
                await load()
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Action failed')
            } finally {
                setActionBusy(null)
            }
        },
        [load],
    )

    const submitLink = useCallback(async () => {
        if (!linkTarget) return
        await runAction('create', () =>
            apiCreateRelationship(documentId, linkTarget, linkType),
        )
        setLinkTarget(null)
        setAdding(false)
    }, [linkTarget, linkType, documentId, runAction])

    return (
        <section className="card overflow-hidden" aria-label="Related documents">
            <div className="flex items-center justify-between border-b border-ink-100 bg-ink-50/50 px-5 py-3.5">
                <h2 className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-[0.12em] text-ink-500">
                    <Link2 size={13} className="text-indigo-400" />
                    Related documents
                    {relationships != null && relationships.length > 0 && (
                        <span className="rounded-full bg-indigo-50 px-1.5 py-px text-[10.5px] font-bold text-indigo-600">
                            {relationships.length}
                        </span>
                    )}
                </h2>
                {canEdit && !adding && (
                    <button
                        type="button"
                        onClick={() => setAdding(true)}
                        className="btn-ghost px-2.5 py-1.5 text-[12px] font-semibold"
                    >
                        <Plus size={13} />
                        Link document
                    </button>
                )}
            </div>

            <div className="space-y-3 px-5 py-4">
                {error && (
                    <p className="flex items-center gap-2 text-[12.5px] text-rose-600">
                        <AlertCircle size={13} className="shrink-0" />
                        {error}
                    </p>
                )}

                {relationships == null ? (
                    <div className="flex items-center gap-2 py-2 text-[13px] text-ink-400">
                        <Loader2 size={14} className="animate-spin" />
                        Loading links…
                    </div>
                ) : (
                    <>
                        {confirmed.length === 0 && suggestions.length === 0 && !adding && (
                            <p className="py-2 text-[13px] text-ink-400">
                                No linked documents yet.
                                {canEdit && ' Use “Link document” to connect related agreements.'}
                            </p>
                        )}

                        <ul className="space-y-2">
                            {[...suggestions, ...confirmed].map(rel => (
                                <li
                                    key={rel.relationship_id}
                                    className={cn(
                                        'flex items-center gap-3 rounded-xl border px-3.5 py-2.5',
                                        rel.suggested
                                            ? 'border-gold-300/60 bg-gold-50/50'
                                            : 'border-ink-100 bg-white',
                                    )}
                                >
                                    <span
                                        className={cn(
                                            'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
                                            rel.suggested
                                                ? 'bg-gold-100 text-gold-700'
                                                : 'bg-indigo-50 text-indigo-500',
                                        )}
                                    >
                                        <FileText size={14} />
                                    </span>
                                    <div className="min-w-0 flex-1">
                                        <Link
                                            href={`/documents/${rel.other_document_id}`}
                                            className="block truncate text-[13.5px] font-semibold text-ink-800 hover:text-indigo-700"
                                        >
                                            {rel.other_filename}
                                        </Link>
                                        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11.5px] text-ink-400">
                                            <span>
                                                {rel.direction === 'outgoing'
                                                    ? RELATIONSHIP_LABELS[rel.relationship_type]
                                                    : `Referenced by (${RELATIONSHIP_LABELS[rel.relationship_type].toLowerCase()})`}
                                            </span>
                                            <span aria-hidden>·</span>
                                            <span>{docTypeMeta(rel.other_document_type).label}</span>
                                            {rel.suggested && (
                                                <span className="ml-1 inline-flex items-center gap-1 rounded-full bg-gold-100 px-2 py-px text-[10.5px] font-bold text-gold-800">
                                                    <Sparkles size={9} />
                                                    Suggested
                                                </span>
                                            )}
                                        </p>
                                    </div>

                                    {canEdit && (
                                        <div className="flex shrink-0 items-center gap-1.5">
                                            {rel.suggested ? (
                                                <>
                                                    <button
                                                        type="button"
                                                        title="Confirm suggested link"
                                                        disabled={actionBusy === rel.relationship_id}
                                                        onClick={() =>
                                                            void runAction(
                                                                rel.relationship_id,
                                                                () =>
                                                                    apiConfirmRelationship(
                                                                        rel.relationship_id,
                                                                    ),
                                                            )
                                                        }
                                                        className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 ring-1 ring-inset ring-emerald-200 transition-colors hover:bg-emerald-100 disabled:opacity-50"
                                                    >
                                                        {actionBusy ===
                                                        rel.relationship_id ? (
                                                            <Loader2
                                                                size={13}
                                                                className="animate-spin"
                                                            />
                                                        ) : (
                                                            <Check size={13} />
                                                        )}
                                                    </button>
                                                    <button
                                                        type="button"
                                                        title="Dismiss suggestion"
                                                        disabled={actionBusy === rel.relationship_id}
                                                        onClick={() =>
                                                            void runAction(
                                                                rel.relationship_id,
                                                                () =>
                                                                    apiDeleteRelationship(
                                                                        rel.relationship_id,
                                                                    ),
                                                            )
                                                        }
                                                        className="flex h-7 w-7 items-center justify-center rounded-lg bg-ink-50 text-ink-500 ring-1 ring-inset ring-ink-200 transition-colors hover:bg-ink-100 disabled:opacity-50"
                                                    >
                                                        <X size={13} />
                                                    </button>
                                                </>
                                            ) : (
                                                <button
                                                    type="button"
                                                    title="Remove link"
                                                    disabled={actionBusy === rel.relationship_id}
                                                    onClick={() =>
                                                        void runAction(
                                                            rel.relationship_id,
                                                            () =>
                                                                apiDeleteRelationship(
                                                                    rel.relationship_id,
                                                                ),
                                                        )
                                                    }
                                                    className="flex h-7 w-7 items-center justify-center rounded-lg bg-ink-50 text-ink-400 ring-1 ring-inset ring-ink-200 transition-colors hover:bg-rose-50 hover:text-rose-500 disabled:opacity-50"
                                                >
                                                    {actionBusy === rel.relationship_id ? (
                                                        <Loader2
                                                            size={13}
                                                            className="animate-spin"
                                                        />
                                                    ) : (
                                                        <Trash2 size={13} />
                                                    )}
                                                </button>
                                            )}
                                        </div>
                                    )}
                                </li>
                            ))}
                        </ul>

                        {adding && (
                            <div className="animate-fade-up space-y-2.5 rounded-xl border border-indigo-200/70 bg-indigo-50/40 p-3.5">
                                <DocumentSelect
                                    documents={documents}
                                    selectedId={linkTarget}
                                    onSelect={setLinkTarget}
                                    placeholder="Search documents to link…"
                                />
                                <div className="flex flex-wrap items-center gap-2">
                                    <select
                                        value={linkType}
                                        onChange={e =>
                                            setLinkType(e.target.value as RelationshipType)
                                        }
                                        className="field flex-1 py-2 text-[13px]"
                                        aria-label="Relationship type"
                                    >
                                        {RELATIONSHIP_TYPES.map(t => (
                                            <option key={t} value={t}>
                                                {RELATIONSHIP_LABELS[t]}
                                            </option>
                                        ))}
                                    </select>
                                    <button
                                        type="button"
                                        onClick={() => void submitLink()}
                                        disabled={!linkTarget || actionBusy === 'create'}
                                        className="btn-primary px-3.5 py-2 text-[12.5px]"
                                    >
                                        {actionBusy === 'create' ? (
                                            <Loader2 size={13} className="animate-spin" />
                                        ) : (
                                            <ArrowRight size={13} />
                                        )}
                                        Link
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setAdding(false)
                                            setLinkTarget(null)
                                        }}
                                        className="btn-ghost px-3 py-2 text-[12.5px]"
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </section>
    )
}
