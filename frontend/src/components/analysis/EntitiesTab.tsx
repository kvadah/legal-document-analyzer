'use client'

/**
 * Entities tab — extracted entities grouped by type, each navigable to its
 * source page in the viewer (10-frontend-spec.md §4).
 */
import { useMemo } from 'react'
import {
    Building2,
    CalendarDays,
    Landmark,
    MapPin,
    CircleDollarSign,
    UserRound,
} from 'lucide-react'
import type { EntityListResponse } from '@/lib/api-client'
import { CitationLink } from '@/components/analysis/CitationLink'
import { entityGroupLabel } from '@/lib/analysis-meta'

const GROUP_ICONS: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
    company: Building2,
    person: UserRound,
    money: CircleDollarSign,
    date: CalendarDays,
    address: MapPin,
    law_reference: Landmark,
}

function groupIcon(type: string) {
    return GROUP_ICONS[type] ?? Landmark
}

const GROUP_TILE: Record<string, string> = {
    company: 'bg-indigo-50 text-indigo-600 ring-indigo-100',
    person: 'bg-emerald-50 text-emerald-600 ring-emerald-100',
    money: 'bg-amber-50 text-amber-600 ring-amber-100',
    date: 'bg-sky-50 text-sky-600 ring-sky-100',
    address: 'bg-rose-50 text-rose-600 ring-rose-100',
    law_reference: 'bg-violet-50 text-violet-600 ring-violet-100',
}

export default function EntitiesTab({
    entities,
}: {
    entities: EntityListResponse
}) {
    const groups = useMemo(
        () =>
            [...entities.groups].sort((a, b) =>
                a.entity_type.localeCompare(b.entity_type),
            ),
        [entities.groups],
    )

    if (groups.length === 0) {
        return (
            <div className="card p-5 text-[13.5px] text-ink-500">
                No entities were extracted from this document.
            </div>
        )
    }

    return (
        <div className="space-y-3">
            {groups.map((group, gi) => {
                const Icon = groupIcon(group.entity_type)
                return (
                    <section
                        key={group.entity_type}
                        className="card p-4 animate-fade-up"
                        style={{ animationDelay: `${Math.min(gi * 60, 240)}ms` }}
                    >
                        <header className="flex items-center gap-2.5">
                            <span
                                className={`flex h-7 w-7 items-center justify-center rounded-lg text-[11px] font-bold ring-1 ring-inset ${GROUP_TILE[group.entity_type] ?? 'bg-ink-100 text-ink-500 ring-ink-200'}`}
                            >
                                <Icon size={13} />
                            </span>
                            <h3 className="text-[13px] font-bold text-ink-800">
                                {entityGroupLabel(group.entity_type)}
                            </h3>
                            <span className="pill bg-ink-50 text-ink-400 ring-1 ring-inset ring-ink-500/10">
                                {group.items.length}
                            </span>
                        </header>
                        <ul className="mt-3 flex flex-wrap gap-2">
                            {group.items.map(entity => (
                                <li
                                    key={entity.id}
                                    className="group inline-flex max-w-full items-center gap-1.5 rounded-lg border border-ink-100 bg-white px-3 py-1.5 text-[13px] text-ink-700 shadow-[0_1px_2px_rgba(12,21,38,0.04)] transition-colors hover:border-indigo-200 hover:bg-indigo-50/40"
                                >
                                    <span className="min-w-0 truncate font-medium">
                                        {entity.value}
                                    </span>
                                    <CitationLink
                                        pageNumber={entity.page_number}
                                        highlightText={entity.raw_text}
                                    />
                                </li>
                            ))}
                        </ul>
                    </section>
                )
            })}
        </div>
    )
}
