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
    ScrollText,
    Trash2,
    RotateCcw,
    Download,
    TriangleAlert,
    Cpu,
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
    apiCancelOrgDeletion,
    apiExportOrgData,
    apiGetOrgSettings,
    apiGetUsage,
    apiInviteUser,
    apiListAuditLogs,
    apiListDeletedDocuments,
    apiListDocuments,
    apiListUsers,
    apiRestoreDocument,
    apiScheduleOrgDeletion,
    apiUpdateOrgSettings,
    apiUpdateUser,
    downloadBlob,
    type AuditLogOut,
    type DocumentOut,
    type OrgSettingsOut,
    type OrgUserOut,
    type UsageResponse,
    type UserRole,
} from '@/lib/api-client'
import { useAuth } from '@/context/AuthContext'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { StatCard } from '@/components/ui/StatCard'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { formatBytes, timeAgo } from '@/lib/format'
import { cn } from '@/lib/cn'

type Tab = 'users' | 'usage' | 'audit' | 'trash' | 'settings'

const TABS: { id: Tab; label: string; icon: typeof Users }[] = [
    { id: 'users', label: 'Users', icon: Users },
    { id: 'usage', label: 'Usage', icon: BarChart3 },
    { id: 'audit', label: 'Audit log', icon: ScrollText },
    { id: 'trash', label: 'Trash', icon: Trash2 },
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
            <div className="card overflow-x-auto p-0">
                <table className="w-full min-w-[820px] text-left">
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
    const [usage, setUsage] = useState<UsageResponse | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        async function load() {
            try {
                const [docs, stats] = await Promise.all([
                    apiListDocuments(),
                    apiGetUsage(),
                ])
                setDocuments(docs.items)
                setUsage(stats)
            } catch (err) {
                setError(
                    err instanceof Error ? err.message : 'Failed to load usage',
                )
            } finally {
                setLoading(false)
            }
        }
        void load()
    }, [])

    const stats = useMemo(() => {
        const analyzed = documents.filter(d => d.status === 'analysis_ready')
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
        return { analyzed, avgScore }
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
                    value={usage?.documents.total ?? documents.length}
                    hint={
                        usage && usage.documents.deleted > 0
                            ? `${usage.documents.deleted} in trash`
                            : 'uploaded all-time'
                    }
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
                    value={formatBytes(usage?.storage_bytes ?? 0)}
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

            <div className="grid gap-4 lg:grid-cols-2">
                <div className="card p-5">
                    <h3 className="flex items-center gap-2 text-[14.5px] font-semibold text-ink-800">
                        <Cpu size={15} className="text-indigo-500" />
                        LLM usage
                    </h3>
                    <p className="mt-1 text-[13px] text-ink-400">
                        Token consumption across the AI pipeline and Q&amp;A.
                    </p>
                    {usage && usage.llm.calls > 0 ? (
                        <>
                            <div className="mt-4 grid grid-cols-3 gap-3">
                                <div>
                                    <p className="text-[20px] font-bold text-ink-800">
                                        {usage.llm.calls.toLocaleString()}
                                    </p>
                                    <p className="text-[12px] text-ink-400">calls</p>
                                </div>
                                <div>
                                    <p className="text-[20px] font-bold text-ink-800">
                                        {usage.llm.input_tokens.toLocaleString()}
                                    </p>
                                    <p className="text-[12px] text-ink-400">input tokens</p>
                                </div>
                                <div>
                                    <p className="text-[20px] font-bold text-ink-800">
                                        {usage.llm.output_tokens.toLocaleString()}
                                    </p>
                                    <p className="text-[12px] text-ink-400">output tokens</p>
                                </div>
                            </div>
                            <div className="mt-4 divide-y divide-ink-50">
                                {usage.llm.by_stage.map(stage => (
                                    <div
                                        key={stage.stage}
                                        className="flex items-center justify-between py-2 text-[13px]"
                                    >
                                        <span className="font-medium capitalize text-ink-600">
                                            {stage.stage.replace('_', ' ')}
                                        </span>
                                        <span className="text-ink-400">
                                            {stage.calls.toLocaleString()} calls ·{' '}
                                            {(stage.input_tokens + stage.output_tokens).toLocaleString()}{' '}
                                            tokens
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </>
                    ) : (
                        <p className="mt-4 text-[13.5px] text-ink-400">
                            No LLM calls recorded yet.
                        </p>
                    )}
                </div>

                <div className="card p-5">
                    <h3 className="text-[14.5px] font-semibold text-ink-800">
                        Members
                    </h3>
                    <p className="mt-1 text-[13px] text-ink-400">
                        Seats in use in this organisation.
                    </p>
                    <div className="mt-4 grid grid-cols-2 gap-3">
                        <div>
                            <p className="text-[20px] font-bold text-ink-800">
                                {usage?.users.total ?? '—'}
                            </p>
                            <p className="text-[12px] text-ink-400">total members</p>
                        </div>
                        <div>
                            <p className="text-[20px] font-bold text-ink-800">
                                {usage?.users.active ?? '—'}
                            </p>
                            <p className="text-[12px] text-ink-400">active</p>
                        </div>
                    </div>
                    <div className="mt-4 border-t border-ink-50 pt-4">
                        <h4 className="text-[12px] font-bold uppercase tracking-wider text-ink-400">
                            Pipeline status breakdown
                        </h4>
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
            </div>
        </div>
    )
}

// ── Settings tab ─────────────────────────────────────────────────────────────

const LLM_PROVIDERS = [
    { value: '', label: 'Server default' },
    { value: 'anthropic', label: 'Anthropic (Claude)' },
    { value: 'openai', label: 'OpenAI' },
    { value: 'gemini', label: 'Google Gemini' },
]

function SettingsTab({ userCount }: { userCount: number | null }) {
    const { user } = useAuth()
    const [org, setOrg] = useState<OrgSettingsOut | null>(null)
    const [name, setName] = useState('')
    const [retentionDays, setRetentionDays] = useState('30')
    const [auditRetentionDays, setAuditRetentionDays] = useState('730')
    const [llmProvider, setLlmProvider] = useState('')
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)
    const [exporting, setExporting] = useState(false)
    const [confirmDeletion, setConfirmDeletion] = useState(false)
    const [deletionBusy, setDeletionBusy] = useState(false)

    const load = useCallback(async () => {
        try {
            const settings = await apiGetOrgSettings()
            setOrg(settings)
            setName(settings.name)
            setRetentionDays(String(settings.retention_days))
            setAuditRetentionDays(String(settings.audit_retention_days))
            setLlmProvider(settings.llm_provider ?? '')
            setError(null)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load settings')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void load()
    }, [load])

    const save = async (e: FormEvent) => {
        e.preventDefault()
        setSaving(true)
        setError(null)
        setSuccess(null)
        try {
            const updated = await apiUpdateOrgSettings({
                name: name.trim(),
                retention_days: Number(retentionDays),
                audit_retention_days: Number(auditRetentionDays),
                ...(llmProvider ? { llm_provider: llmProvider as 'anthropic' | 'openai' | 'gemini' } : {}),
            })
            setOrg(updated)
            setSuccess('Settings saved.')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Save failed')
        } finally {
            setSaving(false)
        }
    }

    const exportData = async () => {
        setExporting(true)
        setError(null)
        try {
            const { blob, filename } = await apiExportOrgData()
            downloadBlob(blob, filename)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Export failed')
        } finally {
            setExporting(false)
        }
    }

    const scheduleDeletion = async () => {
        setDeletionBusy(true)
        setError(null)
        try {
            const updated = await apiScheduleOrgDeletion()
            setOrg(updated)
            setConfirmDeletion(false)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to schedule deletion')
        } finally {
            setDeletionBusy(false)
        }
    }

    const cancelDeletion = async () => {
        setDeletionBusy(true)
        setError(null)
        try {
            const updated = await apiCancelOrgDeletion()
            setOrg(updated)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to cancel deletion')
        } finally {
            setDeletionBusy(false)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center py-16">
                <Loader2 size={20} className="animate-spin text-primary" />
            </div>
        )
    }

    return (
        <div className="space-y-5">
            {error && (
                <div className="card flex items-center gap-3 border-rose-200 bg-rose-50/60 px-5 py-3.5">
                    <AlertCircle size={16} className="shrink-0 text-rose-500" />
                    <p className="text-[13.5px] text-rose-700">{error}</p>
                </div>
            )}

            {org?.scheduled_deletion_at && (
                <div className="card flex items-start gap-3 border-rose-200 bg-rose-50/60 p-5">
                    <TriangleAlert size={18} className="mt-0.5 shrink-0 text-rose-500" />
                    <div className="flex-1">
                        <p className="text-[14px] font-semibold text-rose-800">
                            Organisation deletion scheduled
                        </p>
                        <p className="mt-1 text-[13px] leading-relaxed text-rose-700">
                            All data (documents, analyses, users, audit logs) will be
                            permanently deleted on{' '}
                            <strong>
                                {new Date(org.scheduled_deletion_at).toLocaleString()}
                            </strong>
                            . You can cancel until then.
                        </p>
                        <button
                            onClick={() => void cancelDeletion()}
                            disabled={deletionBusy}
                            className="btn-secondary mt-3 px-3.5 py-2 text-[13px]"
                        >
                            {deletionBusy ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <RotateCcw size={14} />
                            )}
                            Cancel deletion
                        </button>
                    </div>
                </div>
            )}

            <form onSubmit={save} className="card p-5">
                <h3 className="text-[14.5px] font-semibold text-ink-800">
                    Organisation
                </h3>
                <p className="mt-1 text-[13px] text-ink-400">
                    Profile, data retention, and AI provider preferences.
                </p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    <label className="block">
                        <span className="mb-1.5 block text-[12px] font-bold uppercase tracking-wider text-ink-400">
                            Organisation name
                        </span>
                        <input
                            type="text"
                            required
                            minLength={2}
                            maxLength={255}
                            value={name}
                            onChange={e => setName(e.target.value)}
                            className="field w-full px-3.5 py-2.5 text-[14px]"
                        />
                    </label>
                    <label className="block">
                        <span className="mb-1.5 block text-[12px] font-bold uppercase tracking-wider text-ink-400">
                            LLM provider
                        </span>
                        <select
                            value={llmProvider}
                            onChange={e => setLlmProvider(e.target.value)}
                            className="field w-full px-3.5 py-2.5 text-[14px]"
                        >
                            {LLM_PROVIDERS.map(p => (
                                <option key={p.value} value={p.value}>
                                    {p.label}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label className="block">
                        <span className="mb-1.5 block text-[12px] font-bold uppercase tracking-wider text-ink-400">
                            Trash grace period (days)
                        </span>
                        <input
                            type="number"
                            required
                            min={1}
                            max={3650}
                            value={retentionDays}
                            onChange={e => setRetentionDays(e.target.value)}
                            className="field w-full px-3.5 py-2.5 text-[14px]"
                        />
                        <span className="mt-1.5 block text-[12px] text-ink-400">
                            Deleted documents stay recoverable for this long before
                            being permanently purged.
                        </span>
                    </label>
                    <label className="block">
                        <span className="mb-1.5 block text-[12px] font-bold uppercase tracking-wider text-ink-400">
                            Audit log retention (days)
                        </span>
                        <input
                            type="number"
                            required
                            min={30}
                            max={3650}
                            value={auditRetentionDays}
                            onChange={e => setAuditRetentionDays(e.target.value)}
                            className="field w-full px-3.5 py-2.5 text-[14px]"
                        />
                        <span className="mt-1.5 block text-[12px] text-ink-400">
                            Audit entries older than this are removed by the daily
                            retention job.
                        </span>
                    </label>
                </div>
                <div className="mt-4 flex items-center gap-3">
                    <button
                        type="submit"
                        disabled={saving}
                        className="btn-primary px-4 py-2.5 text-[14px]"
                    >
                        {saving ? (
                            <Loader2 size={15} className="animate-spin" />
                        ) : (
                            <CheckCircle2 size={15} />
                        )}
                        Save settings
                    </button>
                    {success && (
                        <p className="text-[13px] text-emerald-600">{success}</p>
                    )}
                </div>
            </form>

            <div className="card p-5">
                <h3 className="text-[14.5px] font-semibold text-ink-800">
                    Data export
                </h3>
                <p className="mt-1 text-[13px] text-ink-400">
                    Download every document and its analysis as machine-readable
                    JSON — for portability or offboarding.
                </p>
                <button
                    onClick={() => void exportData()}
                    disabled={exporting}
                    className="btn-secondary mt-4 px-4 py-2.5 text-[14px]"
                >
                    {exporting ? (
                        <Loader2 size={15} className="animate-spin" />
                    ) : (
                        <Download size={15} />
                    )}
                    Export organisation data
                </button>
            </div>

            <div className="card border-rose-200/70 p-5">
                <h3 className="flex items-center gap-2 text-[14.5px] font-semibold text-rose-700">
                    <TriangleAlert size={15} />
                    Danger zone
                </h3>
                <p className="mt-1 text-[13px] text-ink-400">
                    Schedule the permanent deletion of this organisation. A
                    mandatory waiting period applies, during which the deletion
                    can be cancelled.
                </p>
                {!confirmDeletion ? (
                    <button
                        onClick={() => setConfirmDeletion(true)}
                        className="mt-4 rounded-lg bg-rose-600 px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-rose-700"
                    >
                        Schedule organisation deletion
                    </button>
                ) : (
                    <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-rose-200 bg-rose-50/60 p-4">
                        <p className="text-[13px] text-rose-700">
                            This will permanently delete all documents, analyses,
                            users, and audit logs after the waiting period. Are you
                            sure?
                        </p>
                        <div className="flex gap-2">
                            <button
                                onClick={() => void scheduleDeletion()}
                                disabled={deletionBusy}
                                className="rounded-lg bg-rose-600 px-3.5 py-2 text-[13px] font-semibold text-white hover:bg-rose-700"
                            >
                                {deletionBusy ? 'Scheduling…' : 'Yes, schedule deletion'}
                            </button>
                            <button
                                onClick={() => setConfirmDeletion(false)}
                                className="btn-secondary px-3.5 py-2 text-[13px]"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                )}
            </div>

            <div className="card p-5">
                <h3 className="text-[14.5px] font-semibold text-ink-800">
                    Your account
                </h3>
                <dl className="mt-4 divide-y divide-ink-50">
                    {[
                        ['Email', user?.email ?? '—'],
                        ['Role', user?.role ?? '—'],
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
        </div>
    )
}

// ── Audit tab ────────────────────────────────────────────────────────────────

const AUDIT_ACTION_FILTERS = [
    { value: '', label: 'All actions' },
    { value: 'auth', label: 'Authentication' },
    { value: 'document', label: 'Documents' },
    { value: 'risk', label: 'Risk changes' },
    { value: 'user', label: 'User management' },
    { value: 'org', label: 'Organisation' },
    { value: 'report', label: 'Reports' },
]

function AuditTab() {
    const [entries, setEntries] = useState<AuditLogOut[]>([])
    const [total, setTotal] = useState(0)
    const [filter, setFilter] = useState('')
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const load = useCallback(async (actionPrefix: string) => {
        setLoading(true)
        try {
            const data = await apiListAuditLogs({ limit: 100 })
            const items = actionPrefix
                ? data.items.filter(e => e.action.startsWith(actionPrefix))
                : data.items
            setEntries(items)
            setTotal(data.total)
            setError(null)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load audit log')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void load(filter)
    }, [filter, load])

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
                <select
                    value={filter}
                    onChange={e => setFilter(e.target.value)}
                    className="field appearance-none px-3.5 py-2 text-[13.5px]"
                    aria-label="Filter audit log by action type"
                >
                    {AUDIT_ACTION_FILTERS.map(f => (
                        <option key={f.value} value={f.value}>
                            {f.label}
                        </option>
                    ))}
                </select>
                <p className="text-[12.5px] text-ink-400">
                    {total.toLocaleString()} recorded events (showing latest{' '}
                    {entries.length})
                </p>
            </div>

            {error && (
                <div className="card flex items-center gap-3 border-rose-200 bg-rose-50/60 px-5 py-3.5">
                    <AlertCircle size={16} className="shrink-0 text-rose-500" />
                    <p className="text-[13.5px] text-rose-700">{error}</p>
                </div>
            )}

            {loading ? (
                <div className="flex items-center justify-center py-16">
                    <Loader2 size={20} className="animate-spin text-primary" />
                </div>
            ) : entries.length === 0 ? (
                <div className="card">
                    <EmptyState
                        icon={ScrollText}
                        title="No audit events"
                        description="Security-relevant actions — sign-ins, document access, admin changes — will appear here."
                    />
                </div>
            ) : (
                <div className="card overflow-x-auto p-0">
                    <table className="w-full min-w-[860px] text-left">
                        <thead>
                            <tr className="border-b border-ink-100 bg-ink-50/50 text-[11px] font-bold uppercase tracking-[0.14em] text-ink-400">
                                <th className="px-5 py-3">When</th>
                                <th className="px-5 py-3">User</th>
                                <th className="px-5 py-3">Action</th>
                                <th className="px-5 py-3">Resource</th>
                                <th className="px-5 py-3">IP</th>
                            </tr>
                        </thead>
                        <tbody>
                            {entries.map(entry => (
                                <tr
                                    key={entry.id}
                                    className="border-b border-ink-50 text-[13px] text-ink-700 last:border-0"
                                >
                                    <td className="whitespace-nowrap px-5 py-3 text-ink-400">
                                        {new Date(entry.created_at).toLocaleString()}
                                    </td>
                                    <td className="px-5 py-3">
                                        <span className="font-medium text-ink-800">
                                            {entry.user_email ?? 'System'}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3">
                                        <span className="rounded-md bg-ink-50 px-2 py-1 font-mono text-[12px] text-ink-600">
                                            {entry.action}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3 text-ink-400">
                                        {entry.resource_type
                                            ? `${entry.resource_type}${
                                                  entry.resource_id
                                                      ? ` · ${entry.resource_id.slice(0, 8)}`
                                                      : ''
                                              }`
                                            : '—'}
                                    </td>
                                    <td className="px-5 py-3 font-mono text-[12px] text-ink-400">
                                        {entry.ip_address ?? '—'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    )
}

// ── Trash tab ────────────────────────────────────────────────────────────────

function TrashTab() {
    const [documents, setDocuments] = useState<DocumentOut[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [pendingId, setPendingId] = useState<string | null>(null)

    const load = useCallback(async () => {
        try {
            const data = await apiListDeletedDocuments()
            setDocuments(data.items)
            setError(null)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load trash')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void load()
    }, [load])

    const restore = async (doc: DocumentOut) => {
        setPendingId(doc.id)
        setError(null)
        try {
            await apiRestoreDocument(doc.id)
            setDocuments(prev => prev.filter(d => d.id !== doc.id))
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Restore failed')
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

    return (
        <div className="space-y-4">
            <div className="card flex items-start gap-3 p-5">
                <Info size={16} className="mt-0.5 shrink-0 text-ink-300" />
                <p className="text-[13px] leading-relaxed text-ink-500">
                    Deleted documents are recoverable here until their purge date,
                    after which the daily retention job removes them permanently
                    (files, analysis, and search index included).
                </p>
            </div>

            {error && (
                <div className="card flex items-center gap-3 border-rose-200 bg-rose-50/60 px-5 py-3.5">
                    <AlertCircle size={16} className="shrink-0 text-rose-500" />
                    <p className="text-[13.5px] text-rose-700">{error}</p>
                </div>
            )}

            {documents.length === 0 ? (
                <div className="card">
                    <EmptyState
                        icon={Trash2}
                        title="Trash is empty"
                        description="Documents you delete land here first and stay recoverable during the grace period."
                    />
                </div>
            ) : (
                <div className="card overflow-x-auto p-0">
                    <table className="w-full min-w-[760px] text-left">
                        <thead>
                            <tr className="border-b border-ink-100 bg-ink-50/50 text-[11px] font-bold uppercase tracking-[0.14em] text-ink-400">
                                <th className="px-5 py-3">Document</th>
                                <th className="px-5 py-3">Deleted</th>
                                <th className="px-5 py-3">Purges</th>
                                <th className="px-5 py-3 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {documents.map(doc => (
                                <tr
                                    key={doc.id}
                                    className="border-b border-ink-50 text-[13px] text-ink-700 last:border-0"
                                >
                                    <td className="px-5 py-3.5">
                                        <span className="font-semibold text-ink-800">
                                            {doc.filename}
                                        </span>
                                        <span className="ml-2 text-[12px] text-ink-400">
                                            {formatBytes(doc.file_size_bytes)}
                                        </span>
                                    </td>
                                    <td className="whitespace-nowrap px-5 py-3.5 text-ink-400">
                                        {doc.deleted_at
                                            ? timeAgo(doc.deleted_at)
                                            : '—'}
                                    </td>
                                    <td className="whitespace-nowrap px-5 py-3.5 text-ink-400">
                                        {doc.purges_at
                                            ? new Date(
                                                  doc.purges_at,
                                              ).toLocaleDateString()
                                            : '—'}
                                    </td>
                                    <td className="px-5 py-3.5 text-right">
                                        <button
                                            onClick={() => void restore(doc)}
                                            disabled={pendingId === doc.id}
                                            className="btn-secondary px-3 py-1.5 text-[12.5px]"
                                        >
                                            {pendingId === doc.id ? (
                                                <Loader2
                                                    size={13}
                                                    className="animate-spin"
                                                />
                                            ) : (
                                                <RotateCcw size={13} />
                                            )}
                                            Restore
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
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

                <div className="flex w-fit max-w-full gap-1.5 overflow-x-auto rounded-xl border border-ink-100 bg-white p-1.5 shadow-soft">
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
                {tab === 'audit' && <AuditTab />}
                {tab === 'trash' && <TrashTab />}
                {tab === 'settings' && <SettingsTab userCount={userCount} />}
            </div>
        </AppLayout>
    )
}
