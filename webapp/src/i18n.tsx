import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'

export type Language = 'en' | 'fr'

const LANGUAGE_KEY = 'nb-bias-detector-language-v1'

const messages = {
  en: {
    'app.skipToContent': 'Skip to Main Content',
    'app.nav.profile': 'Profile',
    'app.nav.insights': 'Insights',
    'app.nav.coaching': 'Coaching',
    'app.nav.history': 'History',
    'app.about': 'About Us',
    'app.language.toggle': 'Français',
    'app.hero.eyebrow': 'Trading Bias Detector',
    'app.hero.title': 'Take Control of Trading Decisions',
    'app.hero.subtitle': 'Upload trade history, detect behavioral bias using ML in seconds, and receive personalized coaching for calm, loss-averse, overtrading, and revenge-trading profiles.',
    'app.hero.pill1': 'ML-Powered Analysis',
    'app.hero.pill2': 'Personalized Feedback',
    'app.hero.pill3': 'Real-Time Results',
    'app.input.title': 'Trading History Input',
    'app.input.step1': 'Step 1',
    'app.input.readingFile': 'Reading File...',
    'app.input.uploadFile': 'Upload Trading File',
    'app.input.dropHint': 'Drop a `.csv`, `.xls`, or `.xlsx` file with your trading history.',
    'app.input.ariaUpload': 'Upload trade file',
    'app.input.requiredFields': 'Required fields: timestamp, buy/sell, asset, quantity, entry/exit, P/L, account balance.',
    'app.uploadNotes.title': 'Before You Upload',
    'app.uploadNotes.item1': 'Use one trade per row.',
    'app.uploadNotes.item2': 'Numbers can include decimals.',
    'app.uploadNotes.item3': 'Missing values are flagged under Data Integrity Notes.',
    'app.loading.title': 'Analyzing Your Trading Data',
    'app.loading.subtitle': 'Processing trades and detecting behavioral patterns...',
    'app.loading.step1': 'Parsing File',
    'app.loading.step2': 'ML Analysis',
    'app.loading.step3': 'Generating Report',
    'app.error.api': 'API Error: {message}. Backend URL: {url}',
    'app.error.fallback': 'Failed to analyze trades',
    'analysis.back': 'Back to Home',
    'analysis.title': 'Analysis Results',
    'analysis.save': 'Save to Local History',
    'analysis.totalTrades': 'Total Trades',
    'analysis.winRate': 'Win Rate',
    'analysis.totalPnL': 'Total P/L',
    'analysis.avgWinLoss': 'Avg Win / Loss',
    'analysis.riskScore': 'Risk Score',
    'analysis.behavioralProfile': 'Behavioral Profile',
    'analysis.activeProfile': 'Active Profile: {trader} · Risk Profile: {risk}',
    'analysis.confidence': 'Confidence: {value}%',
    'analysis.graphicalInsights': 'Graphical Insights',
    'analysis.cumulativeTimeline': 'Cumulative P/L Timeline',
    'analysis.biasScoreComparison': 'Bias Score Comparison',
    'analysis.hourlyActivity': 'Hourly Trading Activity',
    'analysis.winLossRatio': 'Win / Loss Ratio',
    'analysis.pnlDistribution': 'P/L Distribution',
    'analysis.savedHistory': 'Saved Analysis History',
    'analysis.noSavedSessions': 'No saved sessions yet.',
    'analysis.tradesCount': '{count} trades',
    'analysis.needAtLeast2': 'Need at least 2 records.',
    'analysis.notEnoughData': 'Not enough data.',
    'analysis.noPnlData': 'No P/L data.',
    'analysis.winRateSmall': 'win rate',
    'analysis.wins': '{count} wins',
    'analysis.losses': '{count} losses',
    'analysis.pnlAxis': 'P/L ->',
    'bias.calm': 'Calm Discipline',
    'bias.lossAversion': 'Loss Aversion',
    'bias.overtrading': 'Overtrading',
    'bias.revengeTrading': 'Revenge Trading',
    'trader.calm': 'Calm Trader',
    'trader.lossAverse': 'Loss Averse Trader',
    'trader.overtrader': 'Overtrader',
    'trader.revenge': 'Revenge Trader',
    'risk.conservative': 'Conservative',
    'risk.moderate': 'Moderate',
    'risk.aggressive': 'Aggressive',
    'heatmap.title': 'Trading Activity Heatmap',
    'heatmap.density': 'DENSITY:',
    'heatmap.trades': 'Trades',
    'heatmap.pnl': 'PnL',
    'heatmap.avgPnl': 'Avg PnL',
    'heatmap.columns': 'COLUMNS:',
    'heatmap.oneHour': '1 Hour',
    'heatmap.twoHour': '2 Hour',
    'heatmap.fourHour': '4 Hour',
    'heatmap.session': 'Session',
    'heatmap.rows': 'ROWS:',
    'heatmap.dayOfWeek': 'Day of Week',
    'heatmap.legend.loss': 'Loss',
    'heatmap.legend.profit': 'Profit',
    'heatmap.session.asian': 'Asian',
    'heatmap.session.european': 'European',
    'heatmap.session.us': 'US',
    'heatmap.session.after': 'After',
    'day.sun': 'Sun',
    'day.mon': 'Mon',
    'day.tue': 'Tue',
    'day.wed': 'Wed',
    'day.thu': 'Thu',
    'day.fri': 'Fri',
    'day.sat': 'Sat',
    'mapper.section': 'Column Mapping',
    'mapper.select': '-- select --',
    'mapper.status.ok': '{count} columns auto-detected successfully',
    'mapper.status.warn': 'Please map all required (*) fields before proceeding',
    'mapper.cancel': 'Cancel',
    'mapper.analyze': 'Analyze Trades',
    'mapper.field.timestamp': 'Timestamp',
    'mapper.field.side': 'Side (Buy/Sell)',
    'mapper.field.asset': 'Asset / Symbol',
    'mapper.field.quantity': 'Quantity',
    'mapper.field.entryPrice': 'Entry Price',
    'mapper.field.exitPrice': 'Exit Price',
    'mapper.field.profitLoss': 'Profit / Loss',
    'mapper.field.balance': 'Account Balance',
    'evidence.tradesPerHour': '{value} trades/hour',
    'evidence.busiestHour': '{value} trades in busiest hour',
    'evidence.winRate': 'Win rate: {value}%',
    'evidence.avgWinLoss': 'Avg win: ${win} vs avg loss: ${loss}',
    'evidence.pattern': 'Pattern analysis from ML model',
    'evidence.riskAfterLoss': 'Risk behavior after losses detected',
    'evidence.disciplined': 'Disciplined trading pattern',
    'evidence.consistentRisk': 'Consistent risk management',
  },
  fr: {
    'app.skipToContent': 'Passer au contenu principal',
    'app.nav.profile': 'Profil',
    'app.nav.insights': 'Apercus',
    'app.nav.coaching': 'Coaching',
    'app.nav.history': 'Historique',
    'app.about': 'A propos',
    'app.language.toggle': 'English',
    'app.hero.eyebrow': 'Detecteur de biais de trading',
    'app.hero.title': 'Reprenez le controle de vos decisions de trading',
    'app.hero.subtitle': 'Importez votre historique de transactions, detectez les biais comportementaux avec le ML en quelques secondes et recevez un coaching personnalise pour les profils calme, aversion aux pertes, sur-trading et trading de revanche.',
    'app.hero.pill1': 'Analyse propulsee par le ML',
    'app.hero.pill2': 'Retours personnalises',
    'app.hero.pill3': 'Resultats en temps reel',
    'app.input.title': 'Importation de l\'historique de trading',
    'app.input.step1': 'Etape 1',
    'app.input.readingFile': 'Lecture du fichier...',
    'app.input.uploadFile': 'Importer un fichier de trading',
    'app.input.dropHint': 'Deposez un fichier `.csv`, `.xls` ou `.xlsx` contenant votre historique.',
    'app.input.ariaUpload': 'Importer un fichier de transactions',
    'app.input.requiredFields': 'Champs requis : horodatage, achat/vente, actif, quantite, entree/sortie, P/L, solde du compte.',
    'app.uploadNotes.title': 'Avant de televerser',
    'app.uploadNotes.item1': 'Utilisez une transaction par ligne.',
    'app.uploadNotes.item2': 'Les nombres peuvent contenir des decimales.',
    'app.uploadNotes.item3': 'Les valeurs manquantes sont signalees dans les notes d\'integrite des donnees.',
    'app.loading.title': 'Analyse de vos donnees de trading',
    'app.loading.subtitle': 'Traitement des transactions et detection des motifs comportementaux...',
    'app.loading.step1': 'Analyse du fichier',
    'app.loading.step2': 'Analyse ML',
    'app.loading.step3': 'Generation du rapport',
    'app.error.api': 'Erreur API : {message}. URL backend : {url}',
    'app.error.fallback': 'Echec de l\'analyse des transactions',
    'analysis.back': 'Retour a l\'accueil',
    'analysis.title': 'Resultats de l\'analyse',
    'analysis.save': 'Enregistrer dans l\'historique local',
    'analysis.totalTrades': 'Transactions totales',
    'analysis.winRate': 'Taux de reussite',
    'analysis.totalPnL': 'P/L total',
    'analysis.avgWinLoss': 'Gain moyen / Perte moyenne',
    'analysis.riskScore': 'Score de risque',
    'analysis.behavioralProfile': 'Profil comportemental',
    'analysis.activeProfile': 'Profil actif : {trader} · Profil de risque : {risk}',
    'analysis.confidence': 'Confiance : {value}%',
    'analysis.graphicalInsights': 'Apercus graphiques',
    'analysis.cumulativeTimeline': 'Chronologie P/L cumulee',
    'analysis.biasScoreComparison': 'Comparaison des scores de biais',
    'analysis.hourlyActivity': 'Activite de trading horaire',
    'analysis.winLossRatio': 'Ratio gains / pertes',
    'analysis.pnlDistribution': 'Distribution du P/L',
    'analysis.savedHistory': 'Historique des analyses enregistrees',
    'analysis.noSavedSessions': 'Aucune session enregistree pour le moment.',
    'analysis.tradesCount': '{count} transactions',
    'analysis.needAtLeast2': 'Au moins 2 enregistrements sont requis.',
    'analysis.notEnoughData': 'Donnees insuffisantes.',
    'analysis.noPnlData': 'Aucune donnee P/L.',
    'analysis.winRateSmall': 'taux de reussite',
    'analysis.wins': '{count} gains',
    'analysis.losses': '{count} pertes',
    'analysis.pnlAxis': 'P/L ->',
    'bias.calm': 'Discipline calme',
    'bias.lossAversion': 'Aversion aux pertes',
    'bias.overtrading': 'Sur-trading',
    'bias.revengeTrading': 'Trading de revanche',
    'trader.calm': 'Trader calme',
    'trader.lossAverse': 'Trader aversif aux pertes',
    'trader.overtrader': 'Sur-trader',
    'trader.revenge': 'Trader de revanche',
    'risk.conservative': 'Conservateur',
    'risk.moderate': 'Modere',
    'risk.aggressive': 'Agressif',
    'heatmap.title': 'Carte de chaleur de l\'activite de trading',
    'heatmap.density': 'DENSITE :',
    'heatmap.trades': 'Transactions',
    'heatmap.pnl': 'PnL',
    'heatmap.avgPnl': 'PnL moyen',
    'heatmap.columns': 'COLONNES :',
    'heatmap.oneHour': '1 heure',
    'heatmap.twoHour': '2 heures',
    'heatmap.fourHour': '4 heures',
    'heatmap.session': 'Session',
    'heatmap.rows': 'LIGNES :',
    'heatmap.dayOfWeek': 'Jour de la semaine',
    'heatmap.legend.loss': 'Perte',
    'heatmap.legend.profit': 'Profit',
    'heatmap.session.asian': 'Asiatique',
    'heatmap.session.european': 'Europeenne',
    'heatmap.session.us': 'US',
    'heatmap.session.after': 'Apres',
    'day.sun': 'Dim',
    'day.mon': 'Lun',
    'day.tue': 'Mar',
    'day.wed': 'Mer',
    'day.thu': 'Jeu',
    'day.fri': 'Ven',
    'day.sat': 'Sam',
    'mapper.section': 'Correspondance des colonnes',
    'mapper.select': '-- selectionner --',
    'mapper.status.ok': '{count} colonnes detectees automatiquement avec succes',
    'mapper.status.warn': 'Veuillez mapper tous les champs requis (*) avant de continuer',
    'mapper.cancel': 'Annuler',
    'mapper.analyze': 'Analyser les transactions',
    'mapper.field.timestamp': 'Horodatage',
    'mapper.field.side': 'Cote (Achat/Vente)',
    'mapper.field.asset': 'Actif / Symbole',
    'mapper.field.quantity': 'Quantite',
    'mapper.field.entryPrice': 'Prix d\'entree',
    'mapper.field.exitPrice': 'Prix de sortie',
    'mapper.field.profitLoss': 'Profit / Perte',
    'mapper.field.balance': 'Solde du compte',
    'evidence.tradesPerHour': '{value} transactions/heure',
    'evidence.busiestHour': '{value} transactions pendant l\'heure la plus active',
    'evidence.winRate': 'Taux de reussite : {value}%',
    'evidence.avgWinLoss': 'Gain moyen : ${win} vs perte moyenne : ${loss}',
    'evidence.pattern': 'Analyse des motifs issue du modele ML',
    'evidence.riskAfterLoss': 'Comportement a risque detecte apres des pertes',
    'evidence.disciplined': 'Schema de trading discipline',
    'evidence.consistentRisk': 'Gestion du risque coherente',
  },
} as const

type MessageKey = keyof typeof messages.en
type TranslationValues = Record<string, string | number>

function interpolate(template: string, values: TranslationValues = {}) {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(values[key] ?? `{${key}}`))
}

interface I18nContextValue {
  language: Language
  setLanguage: (language: Language) => void
  toggleLanguage: () => void
  t: (key: MessageKey, values?: TranslationValues) => string
  formatDateTime: (timestamp: string) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

function getInitialLanguage(): Language {
  const stored = localStorage.getItem(LANGUAGE_KEY)
  if (stored === 'en' || stored === 'fr') return stored
  return 'en'
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(getInitialLanguage)

  const setLanguage = (next: Language) => {
    setLanguageState(next)
    localStorage.setItem(LANGUAGE_KEY, next)
  }

  const value = useMemo<I18nContextValue>(() => {
    const t = (key: MessageKey, values?: TranslationValues) => interpolate(messages[language][key], values)

    const formatDateTime = (timestamp: string) => {
      const date = new Date(timestamp)
      if (Number.isNaN(date.getTime())) return timestamp
      return date.toLocaleString(language === 'fr' ? 'fr-CA' : 'en-CA')
    }

    return {
      language,
      setLanguage,
      toggleLanguage: () => setLanguage(language === 'en' ? 'fr' : 'en'),
      t,
      formatDateTime,
    }
  }, [language])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used inside I18nProvider')
  }
  return context
}

export function getTraderTypeLabel(traderType: string, t: I18nContextValue['t']) {
  if (traderType === 'Calm Trader') return t('trader.calm')
  if (traderType === 'Loss Averse Trader') return t('trader.lossAverse')
  if (traderType === 'Overtrader') return t('trader.overtrader')
  if (traderType === 'Revenge Trader') return t('trader.revenge')
  return traderType
}

export function getRiskLabel(label: string, t: I18nContextValue['t']) {
  if (label === 'Conservative') return t('risk.conservative')
  if (label === 'Moderate') return t('risk.moderate')
  if (label === 'Aggressive') return t('risk.aggressive')
  return label
}

export function getBiasLabel(key: string, t: I18nContextValue['t']) {
  if (key === 'calm') return t('bias.calm')
  if (key === 'lossAversion') return t('bias.lossAversion')
  if (key === 'overtrading') return t('bias.overtrading')
  if (key === 'revengeTrading') return t('bias.revengeTrading')
  return key
}

export function translateEvidenceLine(line: string, t: I18nContextValue['t']) {
  const tradesPerHour = line.match(/^([\d.]+) trades\/hour$/)
  if (tradesPerHour) return t('evidence.tradesPerHour', { value: tradesPerHour[1] })

  const busiestHour = line.match(/^(\d+) trades in busiest hour$/)
  if (busiestHour) return t('evidence.busiestHour', { value: busiestHour[1] })

  const winRate = line.match(/^Win rate: ([\d.]+)%$/)
  if (winRate) return t('evidence.winRate', { value: winRate[1] })

  const avgWinLoss = line.match(/^Avg win: \$([\d.]+) vs avg loss: \$([\d.]+)$/)
  if (avgWinLoss) return t('evidence.avgWinLoss', { win: avgWinLoss[1], loss: avgWinLoss[2] })

  if (line === 'Pattern analysis from ML model') return t('evidence.pattern')
  if (line === 'Risk behavior after losses detected') return t('evidence.riskAfterLoss')
  if (line === 'Disciplined trading pattern') return t('evidence.disciplined')
  if (line === 'Consistent risk management') return t('evidence.consistentRisk')

  return line
}
