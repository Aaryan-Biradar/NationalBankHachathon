import { useEffect, useState } from 'react'
import './index.css'
import AnalysisPage from './AnalysisPage'
import { API_BASE_URL, analyzeTrading, getTrades, mapApiResponseToAnalysis, uploadTradingHistory } from './lib/api'
import type { AnalysisResult, SessionHistoryItem, TraderType } from './types'
import { useI18n } from './i18n'

const HISTORY_KEY = 'nb-bias-detector-history-v1'

function loadHistoryDeferred(onLoaded: (items: SessionHistoryItem[]) => void) {
  const timer = window.setTimeout(() => {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (!raw) return

    try {
      const parsed = JSON.parse(raw) as SessionHistoryItem[]
      onLoaded(parsed.slice(0, 8))
    } catch {
      localStorage.removeItem(HISTORY_KEY)
    }
  }, 0)

  return () => window.clearTimeout(timer)
}

function persistHistoryDeferred(items: SessionHistoryItem[]) {
  const payload = JSON.stringify(items)
  const idleCallback = (window as typeof window & { requestIdleCallback?: (cb: () => void) => number }).requestIdleCallback

  if (idleCallback) {
    idleCallback(() => {
      localStorage.setItem(HISTORY_KEY, payload)
    })
    return
  }

  window.setTimeout(() => {
    localStorage.setItem(HISTORY_KEY, payload)
  }, 0)
}

const traderPalette: Record<TraderType, string> = {
  'Calm Trader': '#087A67',
  'Loss Averse Trader': '#C17A00',
  Overtrader: '#D93236',
  'Revenge Trader': '#8E2E1A',
}

type Page = 'home' | 'analysis'

function App() {
  const { t, toggleLanguage } = useI18n()
  const [page, setPage] = useState<Page>('home')
  const [isParsing, setIsParsing] = useState(false)
  const [fileInputKey, setFileInputKey] = useState(0)
  const [tradesCount, setTradesCount] = useState(0)
  const [parseIssues, setParseIssues] = useState<string[]>([])
  const [history, setHistory] = useState<SessionHistoryItem[]>([])
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)

  useEffect(() => {
    return loadHistoryDeferred(setHistory)
  }, [])

  const handleFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (isParsing) return

    const input = event.currentTarget
    const file = input.files?.[0]
    if (!file) return

    setIsParsing(true)
    setParseIssues([])
    
    try {
      // Upload file directly to API
      const sessionId = await uploadTradingHistory(file)

      // Avoid waterfall: fetch both endpoints in parallel
      const [apiResponse, fetchedTrades] = await Promise.all([
        analyzeTrading(sessionId),
        getTrades(sessionId),
      ])
      
      // Map API response to frontend format
      const result = mapApiResponseToAnalysis(apiResponse, fetchedTrades)
      
      setTradesCount(fetchedTrades.length)
      setAnalysis(result)
      
      if (result) {
        setPage('analysis')
        window.scrollTo(0, 0)
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('app.error.fallback')
      setParseIssues([t('app.error.api', { message: errorMessage, url: API_BASE_URL })])
      setTradesCount(0)
      setAnalysis(null)
    } finally {
      setIsParsing(false)
      input.value = ''
      setFileInputKey((v) => v + 1)
    }
  }

  const saveSession = () => {
    if (!analysis) return
    const { trades: _trades, ...analysisForHistory } = analysis
    const newItem: SessionHistoryItem = {
      id: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
      traderType: analysis.traderType,
      tradesCount: tradesCount || analysis.metrics.totalTrades,
      analysis: analysisForHistory as AnalysisResult,
    }
    const updated = [newItem, ...history].slice(0, 8)
    setHistory(updated)
    persistHistoryDeferred(updated)
  }

  const goHome = () => {
    setPage('home')
    setAnalysis(null)
    setTradesCount(0)
    setParseIssues([])
    window.scrollTo(0, 0)
  }

  const personaAccent = analysis ? traderPalette[analysis.traderType] : '#D6001C'

  return (
    <div className="app-shell" style={{ '--accent-color': personaAccent } as React.CSSProperties}>
      <a className="skip-link" href="#main-content">
        {t('app.skipToContent')}
      </a>
      <header className="nb-header">
        <div className="nb-topbar">
          <div className="nb-logo" aria-label="National Bank Bias Detector" onClick={goHome} style={{ cursor: 'pointer' }}>
            <span className="nb-logo-mark" aria-hidden="true" />
            <span>Sentinel</span>
          </div>
          <nav aria-label="Main" className="nb-mainnav">
            {page === 'home' ? (
              <a href="#trading-input"> </a>
            ) : (
                <>
                <a href="#behavioral-profile">{t('app.nav.profile')}</a>
                <a href="#graphical-insights">{t('app.nav.insights')}</a>
                <a href="#coaching-plan">{t('app.nav.coaching')}</a>
                <a href="#saved-history">{t('app.nav.history')}</a>
              </>
            )}
          </nav>
          <div className="nb-topbar-right">
            <a href="#">{t('app.about')}</a>
            <button className="nb-signin" type="button" onClick={toggleLanguage}>
              {t('app.language.toggle')}
            </button>
          </div>
        </div>
      </header>
      <div className="texture" />

      {page === 'home' && (
        <>
          <section className="hero">
            <div className="hero-copy">
              <p className="eyebrow">{t('app.hero.eyebrow')}</p>
              <h1>{t('app.hero.title')}</h1>
              <p>
                {t('app.hero.subtitle')}
              </p>
              <div className="pill-row">
                <span>{t('app.hero.pill1')}</span>
                <span>{t('app.hero.pill2')}</span>
                <span>{t('app.hero.pill3')}</span>
              </div>
            </div>
          </section>
          <main id="main-content" className="layout">
            <section id="trading-input" className="card controls">
              <h2>{t('app.input.title')}</h2>
              <div className="control-grid">
                <label className="upload-zone">
                  <span className="upload-kicker">{t('app.input.step1')}</span>
                  <strong>{isParsing ? t('app.input.readingFile') : t('app.input.uploadFile')}</strong>
                  <span>{t('app.input.dropHint')}</span>
                  <input
                    key={fileInputKey}
                    className="file-input"
                    type="file"
                    name="trade-file"
                    aria-label={t('app.input.ariaUpload')}
                    accept=".csv,.xlsx,.xls"
                    onChange={handleFile}
                  />
                  <small>{t('app.input.requiredFields')}</small>
                </label>
                <article className="upload-notes" aria-label={t('app.uploadNotes.title')}>
                  <h3>{t('app.uploadNotes.title')}</h3>
                  <ul>
                    <li>{t('app.uploadNotes.item1')}</li>
                    <li>{t('app.uploadNotes.item2')}</li>
                    <li>{t('app.uploadNotes.item3')}</li>
                  </ul>
                  <p>
                    Example: 2025-03-01 9:30,NFLX,SELL,4,1754.20,1756.06,7.36,10007.36
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
          </main>
        </>
      )}

      {page === 'analysis' && analysis && (
        <AnalysisPage
          analysis={analysis}
          history={history}
          onBack={goHome}
          onSave={saveSession}
          onLoadHistory={(a) => setAnalysis(a)}
        />
      )}

      {isParsing && (
        <div className="loading-overlay">
          <div className="loading-container">
            <div className="spinner" />
            <h2 className="loading-title">{t('app.loading.title')}</h2>
            <p className="loading-subtitle">{t('app.loading.subtitle')}</p>
            <div className="progress-steps">
              <div className="progress-step active">
                <span className="step-number">1</span>
                <span className="step-label">{t('app.loading.step1')}</span>
              </div>
              <div className="progress-step active">
                <span className="step-number">2</span>
                <span className="step-label">{t('app.loading.step2')}</span>
              </div>
              <div className="progress-step">
                <span className="step-number">3</span>
                <span className="step-label">{t('app.loading.step3')}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
