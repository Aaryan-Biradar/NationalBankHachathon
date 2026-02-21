import { useEffect, useMemo, useState } from 'react'
import './index.css'
import { analyzeTrades } from './lib/analysis'
import { parseTradeFile } from './lib/parsers'
import type { AnalysisResult, SessionHistoryItem, Trade, TraderType } from './types'

const HISTORY_KEY = 'nb-bias-detector-history-v1'

const traderPalette: Record<TraderType, string> = {
  'Calm Trader': '#087A67',
  'Loss Averse Trader': '#C17A00',
  Overtrader: '#D93236',
  'Revenge Trader': '#8E2E1A',
}

const round = (value: number) => Math.round(value * 100) / 100

const toPolyline = (values: number[]) => {
  if (!values.length) return ''
  const max = Math.max(...values)
  const min = Math.min(...values)
  const spread = Math.max(1, max - min)
  return values
    .map((value, index) => {
      const x = (index / Math.max(1, values.length - 1)) * 100
      const y = 100 - ((value - min) / spread) * 100
      return `${x},${y}`
    })
    .join(' ')
}

const formatDate = (timestamp: string) => {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return timestamp
  return date.toLocaleString()
}

function App() {
  const [isParsing, setIsParsing] = useState(false)
  const [trades, setTrades] = useState<Trade[]>([])
  const [parseIssues, setParseIssues] = useState<string[]>([])
  const [history, setHistory] = useState<SessionHistoryItem[]>([])
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)

  useEffect(() => {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (!raw) return
    try {
      const parsed = JSON.parse(raw) as SessionHistoryItem[]
      setHistory(parsed.slice(0, 8))
    } catch {
      localStorage.removeItem(HISTORY_KEY)
    }
  }, [])

  const handleFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setIsParsing(true)
    try {
      const outcome = await parseTradeFile(file)
      setTrades(outcome.trades)
      setParseIssues(outcome.issues)
      setAnalysis(outcome.trades.length ? analyzeTrades(outcome.trades) : null)
    } catch {
      setParseIssues(['Failed to parse file. Please check format and retry.'])
      setTrades([])
      setAnalysis(null)
    } finally {
      setIsParsing(false)
      event.target.value = ''
    }
  }

  const saveSession = () => {
    if (!analysis || !trades.length) return
    const newItem: SessionHistoryItem = {
      id: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
      traderType: analysis.traderType,
      tradesCount: trades.length,
      analysis,
    }
    const updated = [newItem, ...history].slice(0, 8)
    setHistory(updated)
    localStorage.setItem(HISTORY_KEY, JSON.stringify(updated))
  }

  const personaAccent = analysis ? traderPalette[analysis.traderType] : '#D6001C'

  const sparklinePath = useMemo(() => {
    const values = analysis?.chartData.cumulativePnL ?? []
    if (values.length < 2) return ''
    return toPolyline(values)
  }, [analysis])

  return (
    <div className="app-shell" style={{ '--accent-color': personaAccent } as React.CSSProperties}>
      <a className="skip-link" href="#main-content">
        Skip to Main Content
      </a>
      <header className="nb-header">
        <div className="nb-topbar">
          <nav aria-label="Audience" className="nb-topnav">
            <a href="#">Personal</a>
            <a href="#">Business</a>
            <a href="#">Wealth Management</a>
            <a href="#">About Us</a>
          </nav>
          <button className="nb-signin" type="button">
            Sign In
          </button>
        </div>
        <div className="nb-mainbar">
          <div className="nb-logo" aria-label="National Bank Bias Detector">
            <span className="nb-logo-mark" aria-hidden="true" />
            <span>National Bank</span>
          </div>
          <nav aria-label="Main" className="nb-mainnav">
            <a href="#trading-input">Bias Detection</a>
            <a href="#graphical-insights">Insights</a>
            <a href="#coaching-plan">Coaching</a>
            <a href="#saved-history">History</a>
          </nav>
        </div>
      </header>
      <div className="texture" />
      <main id="main-content" className="layout">
        <section className="hero card">
          <div className="hero-copy">
            <p className="eyebrow">National Bank Bias Detector</p>
            <h1>Take Control of Trading Decisions</h1>
            <p>
              Upload trade history, detect behavioral bias in seconds, and receive personalized coaching for
              calm, loss-averse, overtrading, and revenge-trading profiles.
            </p>
            <div className="pill-row">
              <span>Behavioral Finance Grounded</span>
              <span>Personalized Feedback</span>
              <span>Fast Analysis</span>
            </div>
          </div>
          <div className="hero-panel">
            <p>What You Get</p>
            <ul>
              <li>Mandatory Bias Detection for 3 key behaviors</li>
              <li>Actionable recommendations tied to your data</li>
              <li>Visual timeline and activity heatmap</li>
            </ul>
          </div>
        </section>

        <section id="trading-input" className="card controls">
          <h2>Trading History Input</h2>
          <div className="control-grid">
            <label className="upload-zone">
              <span className="upload-kicker">Step 1</span>
              <strong>{isParsing ? 'Parsing File…' : 'Upload Trading File'}</strong>
              <span>Drop a `.csv`, `.xls`, or `.xlsx` file with your trading history.</span>
              <input
                className="file-input"
                type="file"
                name="trade-file"
                aria-label="Upload trade file"
                accept=".csv,.xlsx,.xls"
                onChange={handleFile}
              />
              <small>Required fields: timestamp, buy/sell, asset, quantity, entry/exit, P/L, account balance.</small>
            </label>
            <article className="upload-notes" aria-label="Upload notes">
              <h3>Before You Upload</h3>
              <ul>
                <li>Use one trade per row.</li>
                <li>Numbers can include decimals.</li>
                <li>Missing values are flagged under Data Integrity Notes.</li>
              </ul>
              <p>
                This keeps the workflow simple and aligned with the challenge: file-based trading history input and
                fast personalized analysis.
              </p>
            </article>
          </div>

          {parseIssues.length > 0 && (
            <ul className="issue-list" aria-live="polite">
              {parseIssues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          )}
        </section>

        {analysis && (
          <>
            <section id="behavioral-profile" className="card">
              <div className="section-head">
                <h2>Behavioral Profile</h2>
                <button className="ghost" type="button" onClick={saveSession}>
                  Save to Local History
                </button>
              </div>
              <p className="profile-line">
                Active Profile: <strong>{analysis.traderType}</strong> · Risk Profile: <strong>{analysis.riskProfile.label}</strong>
              </p>

              <div className="bias-grid">
                {(
                  [
                    ['overtrading', 'Overtrading'],
                    ['lossAversion', 'Loss Aversion'],
                    ['revengeTrading', 'Revenge Trading'],
                    ['calm', 'Calm Discipline'],
                  ] as const
                ).map(([key, label]) => (
                  <article className="bias-card" key={key}>
                    <p>{label}</p>
                    <h3>{round(analysis.biases[key].score)}</h3>
                    <small>Confidence: {round(analysis.biases[key].confidence)}%</small>
                    <ul>
                      {analysis.biases[key].evidence.slice(0, 2).map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            </section>

            <section id="graphical-insights" className="card">
              <h2>Graphical Insights</h2>
              <div className="charts-grid">
                <article className="chart-card">
                  <h3>Cumulative P/L Timeline</h3>
                  {sparklinePath ? (
                    <svg viewBox="0 0 100 100" className="sparkline" preserveAspectRatio="none">
                      <polyline points={sparklinePath} />
                    </svg>
                  ) : (
                    <p className="empty-state">Need at least 2 records to render the timeline.</p>
                  )}
                </article>

                <article className="chart-card">
                  <h3>Trading Heatmap by Hour</h3>
                  <div className="heatmap-grid">
                    {analysis.chartData.hourlyActivity.map((count, hour) => {
                      const intensity = Math.min(1, count / Math.max(1, analysis.metrics.maxHourlyTrades))
                      return (
                        <div
                          className="heatmap-cell"
                          key={hour}
                          style={{ opacity: 0.22 + intensity * 0.78 }}
                          title={`${hour.toString().padStart(2, '0')}:00 — ${count} trades`}
                        >
                          <span>{hour}</span>
                        </div>
                      )
                    })}
                  </div>
                </article>
              </div>
            </section>

            <section id="coaching-plan" className="card recommendations">
              <h2>Personalized Coaching</h2>
              <div className="two-column">
                <div>
                  <h3>Action Plan</h3>
                  <ul>
                    {analysis.recommendations.map((tip) => (
                      <li key={tip}>{tip}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3>Predictive Alerts</h3>
                  <ul>
                    {analysis.predictiveAlerts.length ? (
                      analysis.predictiveAlerts.map((alert) => <li key={alert}>{alert}</li>)
                    ) : (
                      <li>No urgent triggers detected for the latest dataset.</li>
                    )}
                  </ul>

                  <h3>Portfolio Optimization Suggestion</h3>
                  <p>{analysis.portfolioSuggestion}</p>

                  <h3>Data Integrity Notes</h3>
                  <ul>
                    {analysis.qualityIssues.length ? (
                      analysis.qualityIssues.map((issue) => <li key={issue}>{issue}</li>)
                    ) : (
                      <li>No major data quality problems detected.</li>
                    )}
                  </ul>
                </div>
              </div>
            </section>

            <section className="card metrics-row">
              <article>
                <p>Total trades</p>
                <h3>{analysis.metrics.totalTrades}</h3>
              </article>
              <article>
                <p>Win rate</p>
                <h3>{round(analysis.metrics.winRate)}%</h3>
              </article>
              <article>
                <p>Average win / loss</p>
                <h3>
                  ${round(analysis.metrics.averageWin)} / ${round(analysis.metrics.averageLoss)}
                </h3>
              </article>
              <article>
                <p>Trades per hour</p>
                <h3>{round(analysis.metrics.tradesPerHour)}</h3>
              </article>
              <article>
                <p>Risk score</p>
                <h3>{round(analysis.riskProfile.score)}</h3>
              </article>
            </section>
          </>
        )}

        <section id="saved-history" className="card">
          <h2>Saved Analysis History</h2>
          {history.length === 0 ? (
            <p className="empty-state">No saved sessions yet.</p>
          ) : (
            <div className="history-list">
              {history.map((item) => (
                <button
                  key={item.id}
                  className="history-item"
                  type="button"
                  onClick={() => setAnalysis(item.analysis)}
                >
                  <strong>{item.traderType}</strong>
                  <span>{item.tradesCount} trades</span>
                  <span>{formatDate(item.createdAt)}</span>
                </button>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

export default App
