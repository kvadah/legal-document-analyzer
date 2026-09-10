'use client'

import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
    Users,
    Loader2,
    AlertCircle,
    UserPlus,
    ShieldOff,
    CheckCircle2,
    FileStack,
    HardDrive,
    BarChart3,
    Gauge,
    Settings,
    Info,
} from 'lucide-react'
import {
    ResponsiveContainer,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
} from 'recharts'
import AppLayout from '@/app/app-layout'
import {
    apiInviteUser,
    apiListDocuments,
    apiListUsers,
    apiUpdateUser,
    type DocumentOut,
    type OrgUserOut,
    type UserRole,
} from '@/lib/api-client'
import { useAuth } from '@/context/AuthContext'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { StatCard } from '@/components/ui/StatCard'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { formatBytes, timeAgo } from '@/lib/format'
import { cn } from '@/lib/cn'

type Tab = 'users' | 'usage' | 'settings'

const TABS: { id: Tab; label: string; icon: typeof Users }[] = [
    { id: 'users', label: 'Users', icon: Users },
    { id: 'usage', label: 'Usage', icon: BarChart3 },
    { id: 'settings', label: 'Settings', icon: Settings },
]

const ROLE_BADGES: Record<UserRole, string> = {
    admin: 'bg-indigo-50 text-indigo-700 ring-1 ring-inset ring-indigo-600/15',
    reviewer: 'bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-600/15',
    viewer: 'bg-ink-100 text-ink-600 ring-1 ring-inset ring-ink-500/10',
}

// ── Users tab ────────────────────────────────────────────────────────────────

function InviteForm({
    onInvited,
}: {
    onInvited: () => void
}) {
    const [email, setEmail] = useState('')
    const [role, setRole] = useState<'reviewer' | 'viewer'>('reviewer')
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)

    const submit = async (e: FormEvent) => {
        e.preventDefault()
        if (!email.trim()) return
        setBusy(true)
        setError(null)
        setSuccess(null)
        try {
            const result = await apiInviteUser(email.trim(), role)
            setSuccess(result.message)
            setEmail('')
            onInvited()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Invite failed')
        } finally {
            setBusy(false)
        }
    }

    return (
        <form onSubmit={submit} className="card p-5">
            <h3 className="text-[14.5px] font-semibold text-ink-800">
                Invite a member
            </h3>
            <p className="mt-1 text-[13px] text-ink-400">
                They&apos;ll receive a join link and choose a password on
                acceptance.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-2.5">
                <input
                    type="email"
                    required
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="colleague@company.com"
                    className="field min-w-[240px] flex-1 px-3.5 py-2.5 text-[14px]"
                />
                <select
                    value={role}
                    onChange={e =>
                        setRole(e.target.value as 'reviewer' | 'viewer')
                    }
                    className="field px-3 py-2.5 text-[14px]"
                >
                    <option value="reviewer">Reviewer</option>
                    <option value="viewer">Viewer</option>
                </select>
                <button
                    type="submit"
                    disabled={busy || !email.trim()}
                    className="btn-primary px-4 py-2.5 text-[14px]"
                >
                    {busy ? (
                        <Loader2 size={15} className="animate-spin" />
                    ) : (
                        <UserPlus size={15} />
                    )}
                    Invite
                </button>
            </div>
            {error && <p className="mt-3 text-[13px] text-rose-600">{error}</p>}
            {success && (
                <p className="mt-3 text-[13px] text-emerald-600">{success}</p>
            )}
        </form>
    )
}

function UsersTab({
    currentUserId,
    onChanged,
}: {
    currentUserId: string
    onChanged: (users: OrgUserOut[]) => void
}) {
    const [users, setUsers] = useState<OrgUserOut[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [pendingId, setPendingId] = useState<string | null>(null)
    const [actionError, setActionError] = useState<string | null>(null)

    const load = useCallback(async () => {
        try {
            const data = await apiListUsers()
            setUsers(data.items)
            setError(null)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load users')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void load()
    }, [load])

    // Report the fresh list upward (e.g. after invites).
    useEffect(() => {
        if (!loading) onChanged(users)
    }, [users, loading, onChanged])

    const update = async (
        user: OrgUserOut,
        changes: { role?: UserRole; is_active?: boolean },
    ) => {
        setPendingId(user.id)
        setActionError(null)
        // Optimistic update with rollback on failure.
        const previous = users
        setUsers(prev =>
            prev.map(u => (u.id === user.id ? { ...u, ...changes } : u)),
        )
        try {
            const updated = await apiUpdateUser(user.id, changes)
            setUsers(prev =>
                prev.map(u => (u.id === updated.id ? updated : u)),
            )
        } catch (err) {
            setUsers(previous)
            setActionError(
                err instanceof Error ? err.message : 'Update failed',
            )
        } finally {
            setPendingId(null)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center py-16">
                <Loader2 size={20} className="animate-spin text-primary" />
            </div>
        )
    }
    if (error) {
        return (
            <div className="card flex items-center gap-3 border-rose-200 bg-rose-50/60 px-5 py-4">
                <AlertCircle size={18} className="shrink-0 text-rose-500" />
                <p className="text-[14px] text-rose-700">{error}</p>
            </div>
        )
    }

    return (
        <div className="space-y-5">
            <InviteForm onInvited={() => void load()} />
            {actionError && (
                <div className="card flex items-center gap-3 border-rose-200 bg-rose-50/60 px-5 py-3.5">
                    <AlertCircle size={16} className="shrink-0 text-rose-500" />
                    <p className="text-[13.5px] text-rose-700">{actionError}</p>
                </div>
            )}
            <div className="card overflow-hidden p-0">
                <table className="w-full text-left">
                    <thead>
                        <tr className="border-b border-ink-100 bg-ink-50/50 text-[11px] font-bold uppercase tracking-[0.14em] text-ink-400">
                            <th className="px-5 py-3">Member</th>
                            <th className="px-5 py-3">Role</th>
                            <th className="px-5 py-3">Status</th>
                            <th className="px-5 py-3">Last login</th>
                            <th className="px-5 py-3">Joined</th>
                            <th className="px-5 py-3 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map(user => {
                            const isSelf = user.id === currentUserId
                            return (
                                <tr
                                    key={user.id}
                                    className="border-b border-ink-50 text-[13.5px] text-ink-700 last:border-0"
                                >
                                    <td className="px-5 py-3.5">
                                        <span className="font-semibold text-ink-800">
                                            {user.email}
                                        </span>
                                        {isSelf && (
                                            <span className="pill ml-2 bg-indigo-50 text-[10.5px] text-indigo-600">
                                                You
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-5 py-3.5">
                                        <select
                                            value={user.role}
                                            disabled={isSelf || pendingId === user.id}
                                            onChange={e =>
                                                void update(user, {
                                                    role: e.target
                                                        .value as UserRole,
                                                })
                                            }
                                            className={cn(
                                                'rounded-lg px-2.5 py-1.5 text-[12.5px] font-semibold ring-1 ring-inset',
                                                ROLE_BADGES[user.role],
                                                (isSelf || pendingId === user.id) &&
                                                    'opacity-60',
                                            )}
                                        >
                                            <option value="admin">Admin</option>
                                            <option value="reviewer">
                                                Reviewer
                                            </option>
                                            <option value="viewer">Viewer</option>
                                        </select>
                                    </td>
                                    <td className="px-5 py-3.5">
                                        {user.is_active ? (
                                            <span className="pill bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/15">
                                                Active
                                            </span>
                                        ) : (
                                            <span className="pill bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-600/20">
                                                Deactivated
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-5 py-3.5 text-ink-400">
                                        {user.last_login_at
                                            ? timeAgo(user.last_login_at)
                                            : 'Never'}
                                    </td>
                                    <td className="px-5 py-3.5 text-ink-400">
                                        {new Date(
                                            user.created_at,
                                        ).toLocaleDateString(undefined, {
                                            month: 'short',
                                            day: 'numeric',
                                            year: 'numeric',
                                        })}
                                    </td>
                                    <td className="px-5 py-3.5 text-right">
                                        <button
                                            onClick={() =>
                                                void update(user, {
                                                    is_active: !user.is_active,
                                                })
                                            }
                                            disabled={isSelf || pendingId === user.id}
                                            title={
                                                isSelf
                                                    ? 'You cannot deactivate your own account'
                                                    : user.is_active
                                                      ? 'Deactivate'
                                                      : 'Reactivate'
                                            }
                                            className={cn(
                                                'btn-ghost px-3 py-1.5 text-[12.5px]',
                                                user.is_active
                                                    ? 'text-rose-600 hover:bg-rose-50'
                                                    : 'text-emerald-600 hover:bg-emerald-50',
                                            )}
                                        >
                                            {pendingId === user.id ? (
                                                <Loader2
                                                    size={13}
                                                    className="animate-spin"
                                                />
                                            ) : user.is_active ? (
                                                <ShieldOff size={13} />
                                            ) : (
                                                <CheckCircle2 size={13} />
                                            )}
                                            {user.is_active
                                                ? 'Deactivate'
                                                : 'Reactivate'}
                                        </button>
                                    </td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

// ── Usage tab ────────────────────────────────────────────────────────────────

function UsageChartTooltip({
    active,
    payload,
    label,
}: {
    active?: boolean
    payload?: { name?: string; value?: number | string }[]
    label?: string
}) {
    if (!active || !payload?.length) return null
    return (
        <div className="rounded-lg border border-ink-100 bg-white px-3.5 py-2.5 shadow-lift">
            {label && (
                <p className="mb-1 text-[11px] font-bold uppercase tracking-wider text-ink-400">
                    {label}
                </p>
            )}
            <p className="text-[13px] font-semibold text-ink-800">
                Documents: <span className="text-indigo-600">{payload[0]?.value}</span>
            </p>
        </div>
    )
}

function groupByDay(docs: DocumentOut[]) {
    const byDay = new Map<string, number>()
    for (const doc of docs) {
        const day = new Date(doc.created_at).toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric',
        })
        byDay.set(day, (byDay.get(day) ?? 0) + 1)
    }
    return Array.from(byDay.entries())
        .slice(-14)
        .map(([day, count]) => ({ day, count }))
}

function UsageTab() {
    const [documents, setDocuments] = useState<DocumentOut[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        async function load() {
            try {
                const data = await apiListDocuments()
                setDocuments(data.items)
            } catch (err) {
                setError(
                    err instanceof Error ? err.message : 'Failed to load documents',
                )
            } finally {
                setLoading(false)
            }
        }
        void load()
    }, [])

    const stats = useMemo(() => {
        const analyzed = documents.filter(d => d.status === 'analysis_ready')
        const storage = documents.reduce(
            (sum, d) => sum + (d.file_size_bytes ?? 0),
            0,
        )
        const scored = documents.filter(d => d.contract_score != null)
        const avgScore =
            scored.length > 0
                ? Math.round(
                      scored.reduce(
                          (sum, d) => sum + (d.contract_score ?? 0),
                          0,
                      ) / scored.length,
                  )
                : null
        return { analyzed, storage, avgScore }
    }, [documents])

    const timeline = useMemo(() => groupByDay(documents), [documents])

    if (loading) {
        return (
            <div className="flex items-center justify-center py-16">
                <Loader2 size={20} className="animate-spin text-primary" />
            </div>
        )
    }
    if (error) {
        return (
            <div className="card flex items-center gap-3 border-rose-200 bg-rose-50/60 px-5 py-4">
                <AlertCircle size={18} className="shrink-0 text-rose-500" />
                <p className="text-[14px] text-rose-700">{error}</p>
            </div>
        )
    }

    return (
        <div className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard
                    icon={FileStack}
                    label="Documents"
                    value={documents.length}
                    hint="uploaded all-time"
                />
                <StatCard
                    icon={Gauge}
                    label="Analysed"
                    value={stats.analyzed.length}
                    hint="completed the AI pipeline"
                    iconClass="bg-emerald-50 text-emerald-600 ring-emerald-100"
                />
                <StatCard
                    icon={HardDrive}
                    label="Storage used"
                    value={formatBytes(stats.storage)}
                    hint="originals + extracted text"
                    iconClass="bg-gold-50 text-gold-600 ring-gold-100"
                />
                <StatCard
                    icon={Gauge}
                    label="Avg contract score"
                    value={stats.avgScore ?? '—'}
                    hint="across analysed documents"
                    iconClass="bg-sky-50 text-sky-600 ring-sky-100"
                />
            </div>

            <div className="card p-5">
                <h3 className="text-[14.5px] font-semibold text-ink-800">
                    Uploads over time
                </h3>
                <p className="mt-1 text-[13px] text-ink-400">
                    Documents per day, last 14 active days.
                </p>
                <div className="mt-4 h-56">
                    {documents.length === 0 ? (
                        <p className="flex h-full items-center justify-center text-[13.5px] text-ink-400">
                            No documents uploaded yet.
                        </p>
                    ) : (
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={timeline} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
                                <defs>
                                    <linearGradient id="usageFill" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#6366F1" stopOpacity={0.25} />
                                        <stop offset="100%" stopColor="#6366F1" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                                <XAxis
                                    dataKey="day"
                                    tick={{ fontSize: 11, fill: '#94A3B8' }}
                                    axisLine={false}
                                    tickLine={false}
                                />
                                <YAxis
                                    allowDecimals={false}
                                    tick={{ fontSize: 11, fill: '#94A3B8' }}
                                    axisLine={false}
                                    tickLine={false}
                                />
                                <Tooltip content={<UsageChartTooltip />} />
                                <Area
                                    type="monotone"
                                    dataKey="count"
                                    stroke="#6366F1"
                                    strokeWidth={2}
                                    fill="url(#usageFill)"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </div>

            <div className="card p-5">
                <h3 className="text-[14.5px] font-semibold text-ink-800">
                    Pipeline status breakdown
                </h3>
                <div className="mt-3 flex flex-wrap gap-2">
                    {documents.length === 0 && (
                        <p className="text-[13.5px] text-ink-400">
                            Nothing uploaded yet.
                        </p>
                    )}
                    {Object.entries(
                        documents.reduce<Record<string, number>>((acc, doc) => {
                            acc[doc.status] = (acc[doc.status] ?? 0) + 1
                            return acc
                        }, {}),
                    )
                        .sort((a, b) => b[1] - a[1])
                        .map(([status, count]) => (
                            <span
                                key={status}
                                className="inline-flex items-center gap-1.5"
                            >
                                <StatusBadge status={status} />
                                <span className="text-[12px] font-bold text-ink-500">
                                    ×{count}
                                </span>
                            </span>
                        ))}
                </div>
            </div>
        </div>
    )
}

// ── Settings tab ─────────────────────────────────────────────────────────────

function SettingsTab({ userCount }: { userCount: number | null }) {
    const { user } = useAuth()
    return (
        <div className="space-y-5">
            <div className="card p-5">
                <h3 className="text-[14.5px] font-semibold text-ink-800">
                    Organisation
                </h3>
                <dl className="mt-4 divide-y divide-ink-50">
                    {[
                        ['Name', user?.orgName ?? '—'],
                        ['Organisation ID', user?.orgId ?? '—'],
                        ['Members', userCount != null ? String(userCount) : '—'],
                    ].map(([label, value]) => (
                        <div
                            key={label}
                            className="flex items-center justify-between gap-4 py-2.5"
                        >
                            <dt className="text-[13px] font-medium text-ink-400">
                                {label}
                            </dt>
                            <dd className="truncate text-[13.5px] font-semibold text-ink-800">
                                {value}
                            </dd>
                        </div>
                    ))}
                </dl>
            </div>

            <div className="card p-5">
                <h3 className="text-[14.5px] font-semibold text-ink-800">
                    Your account
                </h3>
                <dl className="mt-4 divide-y divide-ink-50">
                    {[
                        ['Email', user?.email ?? '—'],
                        ['Role', user?.role ?? '—'],
                    ].map(([label, value]) => (
                        <div
                            key={label}
                            className="flex items-center justify-between gap-4 py-2.5"
                        >
                            <dt className="text-[13px] font-medium text-ink-400">
                                {label}
                            </dt>
                            <dd className="truncate text-[13.5px] font-semibold text-ink-800">
                                {value}
                            </dd>
                        </div>
                    ))}
                </dl>
            </div>

            <div className="card flex items-start gap-3 p-5">
                <Info size={16} className="mt-0.5 shrink-0 text-ink-300" />
                <p className="text-[13px] leading-relaxed text-ink-500">
                    Retention policy, LLM provider, and feature flags are managed
                    via server configuration (environment variables) and apply
                    instance-wide. Per-organisation editable settings arrive with
                    the Phase 10 hardening pass.
                </p>
            </div>
        </div>
    )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AdminPage() {
    const { user, isLoading: authLoading } = useAuth()
    const [tab, setTab] = useState<Tab>('users')
    const [userCount, setUserCount] = useState<number | null>(null)

    const handleUsersChanged = useCallback((users: OrgUserOut[]) => {
        setUserCount(users.length)
    }, [])

    if (authLoading) {
        return (
            <AppLayout>
                <div className="flex items-center justify-center py-24">
                    <Loader2 size={22} className="animate-spin text-primary" />
                </div>
            </AppLayout>
        )
    }

    if (user?.role !== 'admin') {
        return (
            <AppLayout>
                <PageHeader
                    eyebrow="Insights"
                    title="Administration"
                    description="User management, usage, and organisation settings."
                />
                <EmptyState
                    icon={Settings}
                    title="Admins only"
                    description="This area is restricted to organisation administrators. Ask an admin if you need access."
                />
            </AppLayout>
        )
    }

    return (
        <AppLayout>
            <div className="space-y-6">
                <PageHeader
                    eyebrow="Insights"
                    title="Administration"
                    description="User management, usage, and organisation settings."
                />

                <div className="flex gap-1.5 rounded-xl border border-ink-100 bg-white p-1.5 shadow-soft w-fit">
                    {TABS.map(({ id, label, icon: Icon }) => (
                        <button
                            key={id}
                            onClick={() => setTab(id)}
                            className={cn(
                                'flex items-center gap-2 rounded-lg px-4 py-2 text-[13.5px] font-semibold transition-colors',
                                tab === id
                                    ? 'bg-ink-900 text-white'
                                    : 'text-ink-500 hover:bg-ink-50',
                            )}
                        >
                            <Icon size={15} />
                            {label}
                        </button>
                    ))}
                </div>

                {tab === 'users' && (
                    <UsersTab
                        currentUserId={user.id}
                        onChanged={handleUsersChanged}
                    />
                )}
                {tab === 'usage' && <UsageTab />}
                {tab === 'settings' && <SettingsTab userCount={userCount} />}
            </div>
        </AppLayout>
    )
}
