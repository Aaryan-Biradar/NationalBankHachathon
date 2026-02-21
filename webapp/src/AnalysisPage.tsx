import { memo, useMemo } from 'react'
import type { AnalysisResult, BiasKey, SessionHistoryItem } from './types'
import { getBiasLabel, getRiskLabel, getTraderTypeLabel, useI18n } from './i18n'

const round = (value: number) => Math.round(value * 100) / 100
const fmt = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : n.toFixed(n % 1 === 0 ? 0 : 2)

const BIAS_META: Record<BiasKey, { color: string; icon: string }> = {
    calm: { color: '#087A67', icon: '🧘' },
    lossAversion: { color: '#C17A00', icon: '😰' },
    overtrading: { color: '#D93236', icon: '⚡' },
    revengeTrading: { color: '#8E2E1A', icon: '🔥' },
}

interface AnalysisPageProps {
    analysis: AnalysisResult
    history: SessionHistoryItem[]
    onBack: () => void
    onSave: () => void
    onLoadHistory: (analysis: AnalysisResult) => void
}

/* ─── SVG sub-components ─── */

const CumulativePnLChart = memo(function CumulativePnLChart({ values }: { values: number[] }) {
    const { t } = useI18n()
    if (values.length < 2) return <p className="empty-state">{t('analysis.needAtLeast2')}</p>

    const sampled = useMemo(() => {
        const MAX_PTS = 200
        if (values.length <= MAX_PTS) return values
        const step = (values.length - 1) / (MAX_PTS - 1)
        const out: number[] = []
        for (let i = 0; i < MAX_PTS; i += 1) out.push(values[Math.round(i * step)])
        return out
    }, [values])

    const W = 560, H = 200, PAD = { t: 16, r: 16, b: 28, l: 52 }
    const plotW = W - PAD.l - PAD.r, plotH = H - PAD.t - PAD.b
    let max = -Infinity, min = Infinity
    for (const v of sampled) { if (v > max) max = v; if (v < min) min = v }
    const spread = Math.max(1, max - min)

    const pts = sampled.map((v, i) => ({
        x: PAD.l + (i / (sampled.length - 1)) * plotW,
        y: PAD.t + (1 - (v - min) / spread) * plotH,
    }))
    const line = pts.map(p => `${p.x},${p.y}`).join(' ')
    const area = `${pts[0].x},${PAD.t + plotH} ${line} ${pts[pts.length - 1].x},${PAD.t + plotH}`

    // Y-axis ticks
    const ticks = 5
    const yLabels = Array.from({ length: ticks }, (_, i) => min + (spread * i) / (ticks - 1))

    // Zero line
    const zeroY = min <= 0 && max >= 0 ? PAD.t + (1 - (0 - min) / spread) * plotH : null

    const lastVal = values[values.length - 1]
    const isPositive = lastVal >= 0

    return (
        <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" preserveAspectRatio="xMidYMid meet">
            <defs>
                <linearGradient id="pnl-grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={isPositive ? '#087A67' : '#D93236'} stopOpacity="0.25" />
                    <stop offset="100%" stopColor={isPositive ? '#087A67' : '#D93236'} stopOpacity="0.02" />
                </linearGradient>
            </defs>
            {/* Grid lines */}
            {yLabels.map((v, i) => {
                const y = PAD.t + (1 - (v - min) / spread) * plotH
                return (
                    <g key={i}>
                        <line x1={PAD.l} x2={W - PAD.r} y1={y} y2={y} stroke="var(--line)" strokeWidth="0.5" strokeDasharray="4 3" />
                        <text x={PAD.l - 6} y={y + 4} textAnchor="end" fontSize="10" fill="var(--ink-500)">{fmt(v)}</text>
                    </g>
                )
            })}
            {/* Zero line */}
            {zeroY !== null && (
                <line x1={PAD.l} x2={W - PAD.r} y1={zeroY} y2={zeroY} stroke="var(--ink-500)" strokeWidth="1" strokeDasharray="6 3" opacity="0.5" />
            )}
            {/* Area fill */}
            <polygon points={area} fill="url(#pnl-grad)" />
            {/* Line */}
            <polyline points={line} fill="none" stroke={isPositive ? '#087A67' : '#D93236'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            {/* End dot */}
            <circle cx={pts[pts.length - 1].x} cy={pts[pts.length - 1].y} r="4" fill={isPositive ? '#087A67' : '#D93236'} />
            {/* End label */}
            <text x={pts[pts.length - 1].x} y={pts[pts.length - 1].y - 10} textAnchor="end" fontSize="11" fontWeight="600" fill={isPositive ? '#087A67' : '#D93236'}>
                {isPositive ? '+' : ''}{fmt(lastVal)}
            </text>
        </svg>
    )
})

const BiasScoresChart = memo(function BiasScoresChart({ biases }: { biases: AnalysisResult['biases'] }) {
    const { t } = useI18n()
    const W = 560, H = 200, PAD = { t: 14, r: 24, b: 10, l: 140 }
    const plotW = W - PAD.l - PAD.r
    const keys = Object.keys(BIAS_META) as BiasKey[]
    const barH = 32, gap = 12
    const maxScore = Math.max(...keys.map(k => biases[k].score), 1)

    return (
        <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" preserveAspectRatio="xMidYMid meet">
            {keys.map((key, i) => {
                const { color, icon } = BIAS_META[key]
                const label = getBiasLabel(key, t)
                const score = biases[key].score
                const barW = Math.max(2, (score / maxScore) * plotW)
                const y = PAD.t + i * (barH + gap)
                return (
                    <g key={key}>
                        <text x={PAD.l - 8} y={y + barH / 2 + 4} textAnchor="end" fontSize="12" fill="var(--ink-700)">
                            {icon} {label}
                        </text>
                        {/* Track */}
                        <rect x={PAD.l} y={y} width={plotW} height={barH} rx="6" fill="var(--nb-surface)" />
                        {/* Bar */}
                        <rect x={PAD.l} y={y} width={barW} height={barH} rx="6" fill={color} opacity="0.85" />
                        {/* Score */}
                        <text x={PAD.l + barW + 6} y={y + barH / 2 + 5} fontSize="12" fontWeight="700" fill={color}>
                            {round(score)}
                        </text>
                    </g>
                )
            })}
        </svg>
    )
})

const HourlyActivityChart = memo(function HourlyActivityChart({ data }: { data: number[] }) {
    const W = 560, H = 180, PAD = { t: 14, r: 12, b: 28, l: 32 }
    const plotW = W - PAD.l - PAD.r, plotH = H - PAD.t - PAD.b
    const max = Math.max(...data, 1)
    const barW = plotW / 24 - 3

    return (
        <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" preserveAspectRatio="xMidYMid meet">
            {/* Baseline */}
            <line x1={PAD.l} x2={W - PAD.r} y1={PAD.t + plotH} y2={PAD.t + plotH} stroke="var(--line)" strokeWidth="1" />
            {data.map((count, i) => {
                const barHeight = (count / max) * plotH
                const x = PAD.l + (i / 24) * plotW + 1.5
                const y = PAD.t + plotH - barHeight
                const intensity = count / max
                return (
                    <g key={i}>
                        <rect
                            x={x}
                            y={y}
                            width={barW}
                            height={barHeight}
                            rx="3"
                            fill={`rgba(225, 0, 26, ${0.2 + intensity * 0.65})`}
                        />
                        {i % 3 === 0 && (
                            <text x={x + barW / 2} y={PAD.t + plotH + 14} textAnchor="middle" fontSize="9" fill="var(--ink-500)">
                                {i.toString().padStart(2, '0')}
                            </text>
                        )}
                        {count > 0 && (
                            <text x={x + barW / 2} y={y - 4} textAnchor="middle" fontSize="8" fill="var(--ink-500)">
                                {count}
                            </text>
                        )}
                    </g>
                )
            })}
        </svg>
    )
})

const WinLossDonut = memo(function WinLossDonut({ winRate, totalTrades }: { winRate: number; totalTrades: number }) {
    const { t } = useI18n()
    const size = 160, cx = size / 2, cy = size / 2, r = 56, stroke = 14
    const wins = Math.round((winRate / 100) * totalTrades)
    const losses = totalTrades - wins
    const circumference = 2 * Math.PI * r
    const winArc = (winRate / 100) * circumference

    return (
        <div className="donut-wrapper">
            <svg viewBox={`0 0 ${size} ${size}`} className="donut-svg">
                {/* Loss ring (background) */}
                <circle cx={cx} cy={cy} r={r} fill="none" stroke="#f0e0de" strokeWidth={stroke} />
                {/* Win ring */}
                <circle
                    cx={cx} cy={cy} r={r} fill="none"
                    stroke="#087A67"
                    strokeWidth={stroke}
                    strokeDasharray={`${winArc} ${circumference}`}
                    strokeLinecap="round"
                    transform={`rotate(-90 ${cx} ${cy})`}
                />
                {/* Center text */}
                <text x={cx} y={cy - 4} textAnchor="middle" fontSize="22" fontWeight="700" fill="var(--ink-900)">
                    {round(winRate)}%
                </text>
                <text x={cx} y={cy + 14} textAnchor="middle" fontSize="10" fill="var(--ink-500)">{t('analysis.winRateSmall')}</text>
            </svg>
            <div className="donut-legend">
                <span className="legend-dot legend-win" />
                <span>{t('analysis.wins', { count: wins })}</span>
                <span className="legend-dot legend-loss" />
                <span>{t('analysis.losses', { count: losses })}</span>
            </div>
        </div>
    )
})

const PnLDistribution = memo(function PnLDistribution({ trades }: { trades: AnalysisResult['trades'] }) {
    const { t } = useI18n()
    if (!trades || trades.length < 2) return <p className="empty-state">{t('analysis.notEnoughData')}</p>

    const distribution = useMemo(() => {
        const pnls = trades.map((t) => t.profitLoss ?? 0).filter((v) => v !== 0)
        if (!pnls.length) return null

        let min = Infinity
        let max = -Infinity
        for (const v of pnls) {
            if (v < min) min = v
            if (v > max) max = v
        }

        const bins = 20
        const binW = (max - min) / bins || 1
        const buckets = new Array(bins).fill(0)
        for (const v of pnls) {
            const idx = Math.min(Math.floor((v - min) / binW), bins - 1)
            buckets[idx] += 1
        }

        return {
            min,
            max,
            bins,
            buckets,
            maxCount: Math.max(...buckets, 1),
            zeroBin: min >= 0 ? -1 : Math.min(Math.floor((0 - min) / binW), bins - 1),
        }
    }, [trades])

    if (!distribution) return <p className="empty-state">{t('analysis.noPnlData')}</p>

    const W = 560, H = 150, PAD = { t: 10, r: 12, b: 24, l: 12 }
    const plotW = W - PAD.l - PAD.r, plotH = H - PAD.t - PAD.b
    const bW = plotW / distribution.bins - 2

    return (
        <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" preserveAspectRatio="xMidYMid meet">
            <line x1={PAD.l} x2={W - PAD.r} y1={PAD.t + plotH} y2={PAD.t + plotH} stroke="var(--line)" strokeWidth="1" />
            {distribution.buckets.map((count, i) => {
                const barH = (count / distribution.maxCount) * plotH
                const x = PAD.l + (i / distribution.bins) * plotW + 1
                const y = PAD.t + plotH - barH
                const isNeg = i <= distribution.zeroBin
                return (
                    <rect key={i} x={x} y={y} width={bW} height={barH} rx="2"
                        fill={isNeg ? '#D93236' : '#087A67'} opacity="0.7" />
                )
            })}
            <text x={PAD.l} y={H - 4} fontSize="9" fill="var(--ink-500)">{fmt(distribution.min)}</text>
            <text x={W - PAD.r} y={H - 4} textAnchor="end" fontSize="9" fill="var(--ink-500)">{fmt(distribution.max)}</text>
            <text x={W / 2} y={H - 4} textAnchor="middle" fontSize="9" fill="var(--ink-500)">{t('analysis.pnlAxis')}</text>
        </svg>
    )
})

export default function AnalysisPage({ analysis, history, onBack, onSave, onLoadHistory }: AnalysisPageProps) {
    const { t, formatDateTime } = useI18n()
    const totalPnL = analysis.metrics.totalProfitLoss
    const biasKeys = useMemo(() => Object.keys(BIAS_META) as BiasKey[], [])
    const traderLabel = getTraderTypeLabel(analysis.traderType, t)
    const riskLabel = getRiskLabel(analysis.riskProfile.label, t)

    return (
        <>
            <div className="analysis-topbar">
                <button className="back-btn" type="button" onClick={onBack}>
                    ← {t('analysis.back')}
                </button>
                <h1 className="analysis-title">{t('analysis.title')}</h1>
                <button className="ghost" type="button" onClick={onSave}>
                    {t('analysis.save')}
                </button>
            </div>

            <main id="main-content" className="layout">
                {/* ── Summary Strip ── */}
                <section className="card metrics-row">
                    <article>
                        <p>{t('analysis.totalTrades')}</p>
                        <h3>{analysis.metrics.totalTrades}</h3>
                    </article>
                    <article>
                        <p>{t('analysis.winRate')}</p>
                        <h3>{round(analysis.metrics.winRate)}%</h3>
                    </article>
                    <article>
                        <p>{t('analysis.totalPnL')}</p>
                        <h3 className={totalPnL >= 0 ? 'text-green' : 'text-red'}>
                            {totalPnL >= 0 ? '+' : ''}{fmt(totalPnL)}
                        </h3>
                    </article>
                    <article>
                        <p>{t('analysis.avgWinLoss')}</p>
                        <h3>
                            ${round(analysis.metrics.averageWin)} / ${round(analysis.metrics.averageLoss)}
                        </h3>
                    </article>
                    <article>
                        <p>{t('analysis.riskScore')}</p>
                        <h3>{round(analysis.riskProfile.score)}</h3>
                        <small className="risk-badge">{riskLabel}</small>
                    </article>
                </section>

                {/* ── Behavioral Profile ── */}
                <section id="behavioral-profile" className="card">
                    <h2>{t('analysis.behavioralProfile')}</h2>
                    <p className="profile-line">
                        {t('analysis.activeProfile', { trader: traderLabel, risk: riskLabel })}
                    </p>

                    <div className="bias-grid">
                        {biasKeys.map((key) => {
                            const { color, icon } = BIAS_META[key]
                            const label = getBiasLabel(key, t)
                            const bias = analysis.biases[key]
                            return (
                                <article className="bias-card" key={key} style={{ '--bias-accent': color } as React.CSSProperties}>
                                    <div className="bias-card-header">
                                        <span className="bias-icon">{icon}</span>
                                        <p>{label}</p>
                                    </div>
                                    <h3>{round(bias.score)}</h3>
                                    <div className="bias-bar-track">
                                        <div className="bias-bar-fill" style={{ width: `${Math.min(bias.score, 100)}%`, background: color }} />
                                    </div>
                                    <small>{t('analysis.confidence', { value: round(bias.confidence) })}</small>
                                    <ul>
                                        {bias.evidence.slice(0, 2).map((line) => (
                                            <li key={line}>{line}</li>
                                        ))}
                                    </ul>
                                </article>
                            )
                        })}
                    </div>
                </section>

                {/* ── Graphical Insights ── */}
                <section id="graphical-insights" className="card">
                    <h2>{t('analysis.graphicalInsights')}</h2>

                    <div className="insights-grid">
                        {/* Row 1: P/L Timeline + Bias Scores */}
                        <article className="chart-card chart-wide">
                            <h3>📈 {t('analysis.cumulativeTimeline')}</h3>
                            <CumulativePnLChart values={analysis.chartData.cumulativePnL} />
                        </article>

                        <article className="chart-card chart-wide">
                            <h3>{t('analysis.biasScoreComparison')}</h3>
                            <BiasScoresChart biases={analysis.biases} />
                        </article>

                        {/* Row 2: Hourly Activity + Win/Loss */}
                        <article className="chart-card chart-wide">
                            <h3>🕐 {t('analysis.hourlyActivity')}</h3>
                            <HourlyActivityChart data={analysis.chartData.hourlyActivity} />
                        </article>

                        <article className="chart-card chart-full">
                            <h3>🏆 {t('analysis.winLossRatio')}</h3>
                            <WinLossDonut winRate={analysis.metrics.winRate} totalTrades={analysis.metrics.totalTrades} />
                        </article>

                        {/* Row 3: P/L Distribution */}
                        <article className="chart-card chart-full">
                            <h3>📊 {t('analysis.pnlDistribution')}</h3>
                            <PnLDistribution trades={analysis.trades} />
                        </article>
                    </div>
                </section>

                {/* ── Saved History ── */}
                <section id="saved-history" className="card">
                    <h2>{t('analysis.savedHistory')}</h2>
                    {history.length === 0 ? (
                        <p className="empty-state">{t('analysis.noSavedSessions')}</p>
                    ) : (
                        <div className="history-list">
                            {history.map((item) => (
                                <button
                                    key={item.id}
                                    className="history-item"
                                    type="button"
                                    onClick={() => onLoadHistory(item.analysis)}
                                >
                                    <strong>{getTraderTypeLabel(item.traderType, t)}</strong>
                                    <span>{t('analysis.tradesCount', { count: item.tradesCount })}</span>
                                    <span>{formatDateTime(item.createdAt)}</span>
                                </button>
                            ))}
                        </div>
                    )}
                </section>
            </main>
        </>
    )
}
