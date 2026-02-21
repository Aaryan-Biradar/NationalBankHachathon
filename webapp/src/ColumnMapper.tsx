import { useState } from 'react'
import type { ColumnMapping } from './lib/parsers'
import { FIELD_LABELS, REQUIRED_FIELDS } from './lib/parsers'
import { useI18n } from './i18n'

const FIELDS = Object.keys(FIELD_LABELS)

interface ColumnMapperProps {
    fileName: string
    fileSize: number
    headers: string[]
    initialMapping: ColumnMapping
    onConfirm: (mapping: ColumnMapping) => void
    onCancel: () => void
}

export default function ColumnMapper({
    fileName,
    fileSize,
    headers,
    initialMapping,
    onConfirm,
    onCancel,
}: ColumnMapperProps) {
    const { t } = useI18n()
    const [mapping, setMapping] = useState<ColumnMapping>(initialMapping)
    const fieldLabels: Record<string, string> = {
        timestamp: t('mapper.field.timestamp'),
        side: t('mapper.field.side'),
        asset: t('mapper.field.asset'),
        quantity: t('mapper.field.quantity'),
        entryPrice: t('mapper.field.entryPrice'),
        exitPrice: t('mapper.field.exitPrice'),
        profitLoss: t('mapper.field.profitLoss'),
        balance: t('mapper.field.balance'),
    }

    const autoDetectedCount = Object.keys(initialMapping).length
    const allRequiredMapped = REQUIRED_FIELDS.every((f) => mapping[f])

    const handleChange = (field: string, value: string) => {
        setMapping((prev) => {
            const next = { ...prev }
            if (value === '') {
                delete next[field]
            } else {
                next[field] = value
            }
            return next
        })
    }

    const formatSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    return (
        <section className="card column-mapper">
            <div className="mapper-file-info">
                <div className="mapper-check" aria-hidden="true">✓</div>
                <strong>{fileName}</strong>
                <span className="mapper-size">{formatSize(fileSize)}</span>
            </div>

            <p className="mapper-section-label">{t('mapper.section')}</p>

            <div className="mapper-grid">
                {FIELDS.map((field) => {
                    const isRequired = (REQUIRED_FIELDS as readonly string[]).includes(field)
                    return (
                        <div className="mapper-field" key={field}>
                            <label htmlFor={`map-${field}`}>
                                {fieldLabels[field] ?? FIELD_LABELS[field]}
                                {isRequired && <span className="mapper-req"> *</span>}
                            </label>
                            <select
                                id={`map-${field}`}
                                value={mapping[field] ?? ''}
                                onChange={(e) => handleChange(field, e.target.value)}
                            >
                                <option value="">{t('mapper.select')}</option>
                                {headers.map((h) => (
                                    <option key={h} value={h}>
                                        {h}
                                    </option>
                                ))}
                            </select>
                        </div>
                    )
                })}
            </div>

            <p className={`mapper-status ${allRequiredMapped ? 'mapper-ok' : 'mapper-warn'}`}>
                {allRequiredMapped
                    ? `✓ ${t('mapper.status.ok', { count: autoDetectedCount })}`
                    : `⚠ ${t('mapper.status.warn')}`}
            </p>

            <div className="mapper-actions">
                <button type="button" className="ghost" onClick={onCancel}>
                    {t('mapper.cancel')}
                </button>
                <button
                    type="button"
                    className="mapper-confirm"
                    disabled={!allRequiredMapped}
                    onClick={() => onConfirm(mapping)}
                >
                    {t('mapper.analyze')}
                </button>
            </div>
        </section>
    )
}
