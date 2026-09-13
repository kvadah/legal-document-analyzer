'use client'

/**
 * Comments tab — threaded review discussion scoped to one document
 * (08-feature-spec-collaboration.md §5). Comments can be document-wide or
 * page-anchored (clicking a page anchor jumps the document viewer);
 * resolution tracks the review workflow.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
    CheckCircle2,
    CornerDownRight,
    Loader2,
    MessageSquare,
    MessageSquarePlus,
    SendHorizontal,
    Trash2,
} from 'lucide-react'
import {
    ApiError,
    apiCreateComment,
    apiDeleteComment,
    apiListComments,
    apiUpdateComment,
    type CommentOut,
} from '@/lib/api-client'
import { useAuth } from '@/context/AuthContext'
import { useViewerJump } from '@/components/analysis/CitationLink'
import { cn } from '@/lib/cn'

function authorLabel(comment: CommentOut): string {
    return comment.author_name ?? comment.author_email.split('@')[0]
}

function formatWhen(iso: string): string {
    const date = new Date(iso)
    const now = Date.now()
    const minutes = Math.round((now - date.getTime()) / 60000)
    if (minutes < 1) return 'just now'
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.round(minutes / 60)
    if (hours < 24) return `${hours}h ago`
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

interface CommentItemProps {
    comment: CommentOut
    replies: CommentOut[]
    isOwn: boolean
    canCollaborate: boolean
    onReply: (parentId: string) => void
    onToggleResolved: (comment: CommentOut) => void
    onDelete: (comment: CommentOut) => void
    onJump: (pageNumber: number) => void
}

function CommentItem({
    comment,
    replies,
    isOwn,
    canCollaborate,
    onReply,
    onToggleResolved,
    onDelete,
    onJump,
}: CommentItemProps) {
    return (
        <div className={cn(comment.parent_comment_id && 'ml-6 border-l-2 border-ink-100 pl-4')}>
            <div
                className={cn(
                    'rounded-xl border px-3.5 py-3 transition-colors',
                    comment.resolved
                        ? 'border-emerald-200/70 bg-emerald-50/40'
                        : 'border-ink-100 bg-white',
                )}
            >
                <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-ink-500 to-ink-700 text-[10px] font-bold text-white">
                        {authorLabel(comment).slice(0, 2).toUpperCase()}
                    </span>
                    <span className="truncate text-[13px] font-semibold text-ink-800">
                        {authorLabel(comment)}
                    </span>
                    <span className="shrink-0 text-[11.5px] text-ink-400">
                        {formatWhen(comment.created_at)}
                    </span>
                    {comment.page_number != null && (
                        <button
                            type="button"
                            onClick={() => onJump(comment.page_number!)}
                            title="Jump to this page in the viewer"
                            className="shrink-0 rounded-md bg-indigo-50 px-1.5 py-0.5 text-[10.5px] font-bold text-indigo-600 transition-colors hover:bg-indigo-100"
                        >
                            p.{comment.page_number}
                        </button>
                    )}
                    {comment.resolved && (
                        <span className="ml-auto flex shrink-0 items-center gap-1 text-[11px] font-semibold text-emerald-600">
                            <CheckCircle2 size={12} />
                            Resolved
                        </span>
                    )}
                </div>
                <p className="mt-2 whitespace-pre-wrap text-[13px] leading-relaxed text-ink-700">
                    {comment.content}
                </p>
                {canCollaborate && (
                    <div className="mt-2 flex items-center gap-3 text-[11.5px] font-medium">
                        {!comment.parent_comment_id && (
                            <button
                                type="button"
                                onClick={() => onReply(comment.id)}
                                className="flex items-center gap-1 text-ink-400 transition-colors hover:text-indigo-600"
                            >
                                <CornerDownRight size={12} />
                                Reply
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={() => onToggleResolved(comment)}
                            className={cn(
                                'flex items-center gap-1 transition-colors',
                                comment.resolved
                                    ? 'text-ink-400 hover:text-ink-600'
                                    : 'text-ink-400 hover:text-emerald-600',
                            )}
                        >
                            <CheckCircle2 size={12} />
                            {comment.resolved ? 'Reopen' : 'Resolve'}
                        </button>
                        {(isOwn || canCollaborate) && (
                            <button
                                type="button"
                                onClick={() => onDelete(comment)}
                                className="ml-auto flex items-center gap-1 text-ink-400 transition-colors hover:text-rose-600"
                            >
                                <Trash2 size={12} />
                                Delete
                            </button>
                        )}
                    </div>
                )}
            </div>

            {replies.length > 0 && (
                <div className="mt-2.5 space-y-2.5">
                    {replies.map(reply => (
                        <CommentItem
                            key={reply.id}
                            comment={reply}
                            replies={[]}
                            isOwn={isOwn}
                            canCollaborate={canCollaborate}
                            onReply={onReply}
                            onToggleResolved={onToggleResolved}
                            onDelete={onDelete}
                            onJump={onJump}
                        />
                    ))}
                </div>
            )}
        </div>
    )
}

export default function CommentsTab({ documentId }: { documentId: string }) {
    const { user } = useAuth()
    const canCollaborate = user?.role === 'admin' || user?.role === 'reviewer'
    const jump = useViewerJump()

    const [comments, setComments] = useState<CommentOut[] | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [busy, setBusy] = useState(false)
    const [draft, setDraft] = useState('')
    const [pageAnchor, setPageAnchor] = useState<string>('')
    const [replyTo, setReplyTo] = useState<string | null>(null)
    const listRef = useRef<HTMLDivElement>(null)

    const load = useCallback(async () => {
        try {
            const data = await apiListComments(documentId)
            setComments(data.comments)
            setError(null)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load comments')
        }
    }, [documentId])

    useEffect(() => {
        void load()
    }, [load])

    const submit = useCallback(async () => {
        const content = draft.trim()
        if (!content || busy) return
        setBusy(true)
        try {
            await apiCreateComment(documentId, content, {
                ...(replyTo ? { parent_comment_id: replyTo } : {}),
                ...(pageAnchor.trim() && Number(pageAnchor) >= 1
                    ? { page_number: Number(pageAnchor) }
                    : {}),
            })
            setDraft('')
            setReplyTo(null)
            setPageAnchor('')
            await load()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to add comment')
        } finally {
            setBusy(false)
        }
    }, [busy, documentId, draft, load, pageAnchor, replyTo])

    const toggleResolved = useCallback(
        async (comment: CommentOut) => {
            try {
                await apiUpdateComment(comment.id, { resolved: !comment.resolved })
                await load()
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to update comment')
            }
        },
        [load],
    )

    const remove = useCallback(
        async (comment: CommentOut) => {
            try {
                await apiDeleteComment(comment.id)
                await load()
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to delete comment')
            }
        },
        [load],
    )

    const handleJump = useCallback(
        (pageNumber: number) => {
            jump?.(pageNumber, null)
        },
        [jump],
    )

    // Flat list → one level of threading (top-level + replies).
    const threads = useMemo(() => {
        const all = comments ?? []
        const repliesByParent = new Map<string, CommentOut[]>()
        for (const c of all) {
            if (c.parent_comment_id) {
                const list = repliesByParent.get(c.parent_comment_id) ?? []
                list.push(c)
                repliesByParent.set(c.parent_comment_id, list)
            }
        }
        return all
            .filter(c => !c.parent_comment_id)
            .map(c => ({ comment: c, replies: repliesByParent.get(c.id) ?? [] }))
    }, [comments])

    const openCount = (comments ?? []).filter(c => !c.resolved).length
    const replyTarget = replyTo ? comments?.find(c => c.id === replyTo) : null

    return (
        <div ref={listRef} className="flex h-full flex-col">
            {error && (
                <p className="mb-3 rounded-lg bg-rose-50 px-3 py-2 text-[12.5px] text-rose-700">
                    {error}
                </p>
            )}

            {/* Thread list */}
            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
                {comments === null && (
                    <div className="flex items-center justify-center gap-2 py-10 text-[13px] text-ink-400">
                        <Loader2 size={15} className="animate-spin" />
                        Loading comments…
                    </div>
                )}
                {comments !== null && comments.length === 0 && (
                    <div className="flex flex-col items-center gap-2 py-10 text-center">
                        <MessageSquare size={22} className="text-ink-200" />
                        <p className="text-[13.5px] font-semibold text-ink-600">
                            No comments yet
                        </p>
                        <p className="max-w-xs text-[12.5px] leading-relaxed text-ink-400">
                            {canCollaborate
                                ? 'Start the review discussion — flag clauses, ask questions, track sign-offs.'
                                : 'Team members will see review discussion here.'}
                        </p>
                    </div>
                )}
                {threads.map(({ comment, replies }) => (
                    <CommentItem
                        key={comment.id}
                        comment={comment}
                        replies={replies}
                        isOwn={comment.user_id === user?.id}
                        canCollaborate={canCollaborate}
                        onReply={setReplyTo}
                        onToggleResolved={toggleResolved}
                        onDelete={remove}
                        onJump={handleJump}
                    />
                ))}
            </div>

            {/* Composer */}
            {canCollaborate && (
                <form
                    onSubmit={e => {
                        e.preventDefault()
                        void submit()
                    }}
                    className="mt-3 space-y-2 border-t border-ink-100 pt-3"
                >
                    {replyTarget && (
                        <div className="flex items-center gap-2 rounded-lg bg-indigo-50/70 px-3 py-1.5 text-[12px] text-indigo-700">
                            <CornerDownRight size={12} />
                            Replying to {authorLabel(replyTarget)}
                            <button
                                type="button"
                                onClick={() => setReplyTo(null)}
                                className="ml-auto font-semibold hover:text-indigo-900"
                            >
                                Cancel
                            </button>
                        </div>
                    )}
                    <textarea
                        value={draft}
                        onChange={e => setDraft(e.target.value)}
                        onKeyDown={e => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault()
                                void submit()
                            }
                        }}
                        rows={2}
                        placeholder="Add a review comment… (Enter to post, Shift+Enter for a new line)"
                        disabled={busy}
                        aria-label="Add a comment"
                        className="field resize-none py-2.5 text-[13px]"
                    />
                    <div className="flex items-center gap-2">
                        <input
                            type="number"
                            min={1}
                            value={pageAnchor}
                            onChange={e => setPageAnchor(e.target.value)}
                            placeholder="Page #"
                            aria-label="Anchor comment to a page number"
                            title="Optionally anchor this comment to a page"
                            className="field w-20 px-2.5 py-2 text-center text-[12px]"
                        />
                        <span className="text-[11px] text-ink-400">
                            {openCount > 0
                                ? `${openCount} open comment${openCount === 1 ? '' : 's'}`
                                : 'All comments resolved'}
                        </span>
                        <button
                            type="submit"
                            disabled={busy || !draft.trim()}
                            aria-label="Post comment"
                            className="btn-primary ml-auto h-[38px] w-[38px] shrink-0 p-0"
                        >
                            {busy ? (
                                <Loader2 size={15} className="animate-spin" />
                            ) : replyTo ? (
                                <CornerDownRight size={15} />
                            ) : (
                                <SendHorizontal size={15} />
                            )}
                        </button>
                    </div>
                </form>
            )}
            {!canCollaborate && comments != null && comments.length > 0 && (
                <p className="mt-3 flex items-center gap-1.5 border-t border-ink-100 pt-3 text-[11.5px] text-ink-400">
                    <MessageSquarePlus size={12} />
                    Your role is read-only — reviewers and admins can add comments.
                </p>
            )}
        </div>
    )
}
