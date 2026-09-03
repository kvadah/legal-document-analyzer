import { Scale } from 'lucide-react'
import { cn } from '@/lib/cn'

export function LogoMark({ className, size = 34 }: { className?: string; size?: number }) {
    return (
        <span
            className={cn(
                'relative inline-flex items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-600 text-white shadow-glow',
                className,
            )}
            style={{ width: size, height: size }}
        >
            <Scale size={size * 0.56} strokeWidth={1.9} />
            <span className="pointer-events-none absolute inset-0 rounded-xl ring-1 ring-inset ring-white/25" />
        </span>
    )
}

export function LogoWordmark({ dark = false }: { dark?: boolean }) {
    return (
        <span className="flex items-center gap-2.5">
            <LogoMark size={32} />
            <span className="flex flex-col leading-none">
                <span
                    className={cn(
                        'font-display text-[17px] font-semibold tracking-tight',
                        dark ? 'text-white' : 'text-ink-900',
                    )}
                >
                    Legal Doc <span className="text-gradient">AI</span>
                </span>
                <span
                    className={cn(
                        'mt-1 text-[10px] font-semibold uppercase tracking-[0.22em]',
                        dark ? 'text-ink-300/60' : 'text-ink-400',
                    )}
                >
                    Contract Intelligence
                </span>
            </span>
        </span>
    )
}
