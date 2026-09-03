'use client'

import { ShieldAlert } from 'lucide-react'

export default function Disclaimer() {
    return (
        <div className="flex items-center justify-center gap-2 border-t border-gold-200/70 bg-gradient-to-r from-gold-50/80 via-amber-50/60 to-gold-50/80 px-4 py-1.5 text-center text-[11px] leading-4 text-gold-800">
            <ShieldAlert size={12} className="shrink-0 text-gold-600" />
            <span>
                <span className="font-semibold">Disclaimer:</span> AI-generated analysis is not
                legal advice. Consult a qualified attorney for binding legal decisions.
            </span>
        </div>
    )
}
