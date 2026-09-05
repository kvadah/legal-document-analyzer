'use client'

/**
 * Shared citation component (10-frontend-spec.md §9).
 *
 * Every tab (Summary, Clauses, Risks, Entities, Obligations — and later
 * Q&A / Search) renders citations through this single component. It calls
 * the viewer-jump callback provided by the Analysis page, which scrolls
 * the document viewer to the cited page and highlights the anchor text.
 */
import { createContext, useContext } from 'react'
import { FileText } from 'lucide-react'
import { cn } from '@/lib/cn'

export type ViewerJumpFn = (
    pageNumber: number,
    highlightText?: string | null,
) => void

export const ViewerJumpContext = createContext<ViewerJumpFn | null>(null)

export function useViewerJump(): ViewerJumpFn | null {
    return useContext(ViewerJumpContext)
}

export function CitationLink({
    pageNumber,
    highlightText,
    className,
}: {
    pageNumber: number
    highlightText?: string | null
    className?: string
}) {
    const jump = useViewerJump()
    if (!jump) return null

    return (
        <button
            type="button"
            onClick={() => jump(pageNumber, highlightText)}
            title={`Jump to page ${pageNumber}`}
            className={cn(
                'inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-[11.5px] font-semibold text-indigo-600 transition-colors hover:bg-indigo-50 hover:text-indigo-700',
                className,
            )}
        >
            <FileText size={11.5} strokeWidth={2.2} />
            p.&nbsp;{pageNumber}
        </button>
    )
}
