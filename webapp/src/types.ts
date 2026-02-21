export type TraderType =
  | 'Calm Trader'
  | 'Loss Averse Trader'
  | 'Overtrader'
  | 'Revenge Trader'

export type BiasKey = 'overtrading' | 'lossAversion' | 'revengeTrading' | 'calm'

export interface Trade {
  timestamp: string
  side: 'BUY' | 'SELL'
  asset: string
  quantity: number | null
  entryPrice: number | null
  exitPrice: number | null
  profitLoss: number | null
  balance: number | null
}

export interface ParseOutcome {
  trades: Trade[]
  issues: string[]
}

export interface BiasResult {
  score: number
  confidence: number
  evidence: string[]
}

export interface RiskProfile {
  score: number
  label: 'Conservative' | 'Moderate' | 'Aggressive'
  rationale: string
}

export type HeatmapMode = '1hour' | '2hour' | '4hour' | 'session'

export interface HeatmapModeData {
  cols: number
  sums: number[]
  counts: number[]
}

export interface HeatmapData {
  oneHour: HeatmapModeData
  twoHour: HeatmapModeData
  fourHour: HeatmapModeData
  session: HeatmapModeData
}

export interface PnLDistributionData {
  min: number
  max: number
  buckets: number[]
}

export interface AnalysisResult {
  biases: Record<BiasKey, BiasResult>
  traderType: TraderType
  recommendations: string[]
  predictiveAlerts: string[]
  qualityIssues: string[]
  qualitySummary?: {
    errors: number
    warnings: number
    info: number
  }
  riskProfile: RiskProfile
  portfolioSuggestion: string
  metrics: {
    totalTrades: number
    winRate: number
    averageWin: number
    averageLoss: number
    tradesPerHour: number
    maxHourlyTrades: number
    totalProfitLoss: number
  }
  chartData: {
    cumulativePnL: number[]
    hourlyActivity: number[]
    pnlDistribution: PnLDistributionData
  }
  heatmap?: HeatmapData
  trades?: Trade[]
}

export interface SessionHistoryItem {
  id: string
  createdAt: string
  traderType: TraderType
  tradesCount: number
  analysis: AnalysisResult
}
