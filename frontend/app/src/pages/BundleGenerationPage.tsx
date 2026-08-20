import { startTransition, useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import type { EChartsOption } from 'echarts'
import ReactECharts from 'echarts-for-react'
import {
  AdjustmentsHorizontalIcon,
  ArrowPathIcon,
  ArrowTrendingUpIcon,
  BoltIcon,
  ChartBarIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CpuChipIcon,
  CubeTransparentIcon,
  MegaphoneIcon,
  RocketLaunchIcon,
  ShieldCheckIcon,
  SparklesIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/StateMessage'
import {
  type BundleGeneratorApiResponse,
  type BundleGeneratorRequestPayload,
  type GeneratorBundleType,
  type GeneratorExistingBundleItem,
  type GeneratorGeneratedBundleItem,
  type GeneratorMeta,
  type GeneratorModelParams,
  type OfferType,
  generateBundles,
} from '../services/generator'

type MetricTone = 'mint' | 'sky' | 'gold' | 'rose'

type SelectOption = {
  value: string
  label: string
  hint: string
}

type Stage = {
  title: string
  detail: string
}

type GeneratorFormState = {
  offerType: OfferType
  allowedBundleTypes: GeneratorBundleType[]
  validityOptions: number[]
  maxVolumeMb: string
  maxVolumeMin: string
  maxVolumeSms: string
  samplesPerType: string
  topN: string
}

type GeneratorSummaryRow = {
  new_bundle_id: string
  new_bundle_type: string
  new_price: number
  new_volume_mb: number
  new_volume_min: number
  new_volume_sms: number
  new_validity_days: number
  new_validity_bucket: string
  predicted_popularity: number
  popularity_category: string
  incremental_revenue_weekly: number
  incremental_subs_weekly: number
  total_cannib_revenue_weekly: number
  total_cannib_subs_weekly: number
  net_revenue_weekly: number
  net_revenue_monthly: number
  net_subs_weekly: number
  cannib_pct_of_portfolio: number
  most_cannibalized_bundle_id: string
  most_cannibalized_bundle_name: string
  most_cannibalized_delta_rev: number
  high_risk_count: number
  medium_risk_count: number
  safe_bundle_count: number
}

type GeneratorImpactRow = {
  new_bundle_id: string
  new_bundle_type: string
  new_price: number
  predicted_popularity: number
  existing_bundle_id: string
  existing_bundle_name: string
  existing_bundle_type: string
  existing_price: number
  existing_volume_gb: number
  existing_minutes: number
  existing_sms: number
  existing_avg_rev_weekly: number
  existing_avg_subs_weekly: number
  similarity: number
  cannib_rate: number
  cannib_rate_pct: number
  delta_revenue_weekly: number
  delta_revenue_monthly: number
  delta_subs_weekly: number
  risk_tier: string
}

type GeneratorBundleView = {
  id: string
  generated: GeneratorGeneratedBundleItem
  summary: GeneratorSummaryRow | null
  impacts: GeneratorImpactRow[]
}

type GeneratorDashboardState = {
  request: BundleGeneratorRequestPayload
  meta: GeneratorMeta
  modelParams: GeneratorModelParams
  existingBundles: GeneratorExistingBundleItem[]
  summaries: GeneratorSummaryRow[]
  impacts: GeneratorImpactRow[]
  topPerType: GeneratorSummaryRow[]
  bundleViews: GeneratorBundleView[]
}

type MbaFormState = {
  topK: string
  minFreq: string
  minSupportPct: string
  topNEdges: string
  offerType: OfferType
}

type MbaBundleItem = {
  name: string
  components: Record<string, number>
  validity_days: number
  calculated_price: number
  individual_prices: Record<string, number>
  score: number
  justification: string
}

type MbaBundlesResponse = {
  bundles: MbaBundleItem[]
}

type MbaSankeyNode = {
  name: string
}

type MbaSankeyLink = {
  source: number
  target: number
  value: number
  source_name: string
  target_name: string
  avg_confidence: number
  avg_lift: number
  edge_count: number
  strength_score: number
}

type MbaSankeyEdgeTableItem = {
  source: string
  target: string
  value: number
  avg_confidence: number
  avg_lift: number
  edge_count: number
  strength_score: number
}

type MbaSankeyResponse = {
  nodes: MbaSankeyNode[]
  links: MbaSankeyLink[]
  edge_table: MbaSankeyEdgeTableItem[]
}

const panelClassName =
  'rounded-[2rem] border border-minteal-100 bg-white/90 shadow-[0_30px_80px_-48px_rgba(12,27,27,0.35)]'

const tooltipStyle = {
  backgroundColor: 'rgba(255, 255, 255, 0.98)',
  border: '1px solid #dbe5e5',
  borderRadius: '20px',
  boxShadow: '0 24px 60px rgba(12, 27, 27, 0.12)',
}

const chartGrid = '#dbe5e5'
const chartText = '#4c7c7c'
const chartMintDark = '#0f766e'

const generationStages: Stage[] = [
  {
    title: 'Submitting generator request',
    detail: 'Bundle generation controls are being sent to the FastAPI service.',
  },
  {
    title: 'Generating candidate bundles',
    detail: 'The backend is sampling candidate bundles and scoring portfolio fit.',
  },
  {
    title: 'Computing commercial impact',
    detail: 'Revenue, subscription change, and shortlist rankings are being assembled.',
  },
  {
    title: 'Mapping cannibalization',
    detail: 'Generated bundles are being compared against the existing portfolio.',
  },
]


const DEFAULT_GENERATOR_FORM: GeneratorFormState = {
  offerType: 'atl',
  allowedBundleTypes: ['BUNDLE_DATA', 'BUNDLE_VOICE', 'BUNDLE_SMS'],
  validityOptions: [24, 72, 168, 720],
  maxVolumeMb: '25000',
  maxVolumeMin: '300',
  maxVolumeSms: '150',
  samplesPerType: '500',
  topN: '1',
}

const MBA_DEFAULT_FORM: MbaFormState = {
  topK: '6',
  minFreq: '5000',
  minSupportPct: '0.001',
  topNEdges: '18',
  offerType: 'atl',
}

const API_BASE_URL =
  (import.meta.env.VITE_PRICING_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ??
  'http://127.0.0.1:8000'

const priceOptions: SelectOption[] = [
  { value: 'atl', label: 'ATL', hint: 'Above The Line.' },
  { value: 'btl_normal', label: 'BTL-Normal', hint: 'Below The Line - Normal.' },
  { value: 'btl_moderate', label: 'BTL-Moderate', hint: 'Below The Line - Moderate.' },
  { value: 'btl_aggressive', label: 'BTL-Aggressive', hint: 'Below The Line - Aggressive.' },
  { value: 'promotion_mode', label: 'Promotion Mode', hint: 'Promotion-led commercial mode.' },
  { value: 'diy_mode', label: 'DIY mode', hint: 'Do it Yourself mode.' },
]

const generatorBundleTypeOptions: Array<{ value: GeneratorBundleType; label: string; hint: string }> = [
  { value: 'BUNDLE_DATA', label: 'Bundle Data', hint: 'Generate bundles centered on data allowance.' },
  { value: 'BUNDLE_VOICE', label: 'Bundle Voice', hint: 'Generate bundles centered on voice minutes.' },
  { value: 'BUNDLE_SMS', label: 'Bundle SMS', hint: 'Generate bundles centered on SMS volume.' },
]

const validityOptionsCatalog = [
  { value: 24, label: '24h' },
  { value: 72, label: '72h' },
  { value: 168, label: '7d' },
  { value: 720, label: '30d' },
]

const metricToneStyles: Record<
  MetricTone,
  {
    labelClassName: string
    valueClassName: string
    accentClassName: string
  }
> = {
  mint: {
    labelClassName: 'bg-minteal-50 text-minteal-700',
    valueClassName: 'text-minteal-950',
    accentClassName: 'bg-minteal-500',
  },
  sky: {
    labelClassName: 'bg-sky-50 text-sky-700',
    valueClassName: 'text-sky-950',
    accentClassName: 'bg-sky-400',
  },
  gold: {
    labelClassName: 'bg-amber-50 text-amber-700',
    valueClassName: 'text-amber-950',
    accentClassName: 'bg-amber-400',
  },
  rose: {
    labelClassName: 'bg-rose-50 text-rose-700',
    valueClassName: 'text-rose-950',
    accentClassName: 'bg-rose-400',
  },
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

const roundNumber = (value: number, decimals = 0) => {
  const factor = 10 ** decimals
  return Math.round(value * factor) / factor
}

const compactNumber = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })
const wholeNumber = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const timeFormatter = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' })

const formatCompactCurrency = (value: number) => `Fr ${compactNumber.format(value)}`
const formatWholeCurrency = (value: number) => `Fr ${wholeNumber.format(value)}`

const mbaInputClassName =
  'mt-2 w-full rounded-[1.2rem] border border-minteal-200 bg-white px-4 py-3 text-sm font-medium text-minteal-900 outline-none transition focus:border-minteal-400 focus:ring-2 focus:ring-minteal-200'

const getErrorMessage = (error: unknown) => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail

    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }

    return error.message
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Unexpected error'
}

const parsePositiveInteger = (value: string, fallback: number) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : fallback
}

const parsePositiveFloat = (value: string, fallback: number) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

const fieldInputClassName =
  'mt-2 w-full rounded-[1.2rem] border border-minteal-200 bg-white px-4 py-3 text-sm font-medium text-minteal-900 outline-none transition focus:border-minteal-400 focus:ring-2 focus:ring-minteal-200 disabled:cursor-not-allowed disabled:bg-minteal-50'

const getRecordValue = (record: Record<string, unknown>, aliases: string[]) => {
  for (const alias of aliases) {
    if (alias in record) {
      return record[alias]
    }
  }

  return undefined
}

const pickString = (record: Record<string, unknown>, aliases: string[], fallback = '') => {
  const value = getRecordValue(record, aliases)
  return typeof value === 'string' && value.trim() ? value : fallback
}

const pickNumber = (record: Record<string, unknown>, aliases: string[], fallback = 0) => {
  const value = getRecordValue(record, aliases)
  return typeof value === 'number' && Number.isFinite(value)
    ? value
    : typeof value === 'string' && value.trim() && Number.isFinite(Number(value))
      ? Number(value)
      : fallback
}

const normalizePercentValue = (value: number) => (value <= 1 ? value * 100 : value)

const formatBundleTypeLabel = (bundleType: string) =>
  bundleType
    .replace(/^BUNDLE_/i, '')
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase())

const formatValidityLabel = (days: number, hours: number, bucket?: string | null) => {
  if (bucket === 'monthly' || bucket === 'long_term' || days >= 30) {
    return `${roundNumber(days, 0)} days`
  }

  if (bucket === 'weekly' || days >= 7) {
    return `${roundNumber(days, 0)} days`
  }

  if (bucket === 'daily' || days >= 1) {
    return `${roundNumber(days, 1)} day`
  }

  return `${roundNumber(hours, 0)} hours`
}

const formatRiskTierLabel = (value: string) =>
  value
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase())

const getRiskTierColor = (riskTier: string) => {
  switch (riskTier.toLowerCase()) {
    case 'high':
      return '#fb7185'
    case 'medium':
      return '#f59e0b'
    default:
      return '#14b8a6'
  }
}

const buildGeneratorRequest = (form: GeneratorFormState): BundleGeneratorRequestPayload => ({
  offer_type: form.offerType,
  allowed_bundle_types: form.allowedBundleTypes,
  validity_options: form.validityOptions,
  max_volume_mb: parsePositiveFloat(form.maxVolumeMb, 25000),
  max_volume_min: parsePositiveInteger(form.maxVolumeMin, 300),
  max_volume_sms: parsePositiveInteger(form.maxVolumeSms, 150),
  samples_per_type: parsePositiveInteger(form.samplesPerType, 500),
  top_n: parsePositiveInteger(form.topN, 2),
})

const normalizeSummaryRow = (record: Record<string, unknown>): GeneratorSummaryRow => ({
  new_bundle_id: String(getRecordValue(record, ['new_bundle_id', 'bundle_id', 'generated_bundle_id']) ?? ''),
  new_bundle_type: pickString(record, ['new_bundle_type', 'bundle_type'], 'Unknown'),
  new_price: pickNumber(record, ['new_price', 'price'], 0),
  new_volume_mb: pickNumber(record, ['new_volume_mb', 'volume_mb'], 0),
  new_volume_min: pickNumber(record, ['new_volume_min', 'volume_min', 'minutes'], 0),
  new_volume_sms: pickNumber(record, ['new_volume_sms', 'volume_sms', 'sms'], 0),
  new_validity_days: pickNumber(record, ['new_validity_days', 'validity_days'], 0),
  new_validity_bucket: pickString(record, ['new_validity_bucket', 'validity_bucket'], 'unknown'),
  predicted_popularity: pickNumber(record, ['predicted_popularity', 'popularity_score'], 0),
  popularity_category: pickString(record, ['popularity_category'], 'Unclassified'),
  incremental_revenue_weekly: pickNumber(record, ['incremental_revenue_weekly'], 0),
  incremental_subs_weekly: pickNumber(record, ['incremental_subs_weekly'], 0),
  total_cannib_revenue_weekly: pickNumber(record, ['total_cannib_revenue_weekly'], 0),
  total_cannib_subs_weekly: pickNumber(record, ['total_cannib_subs_weekly'], 0),
  net_revenue_weekly: pickNumber(record, ['net_revenue_weekly'], 0),
  net_revenue_monthly: pickNumber(record, ['net_revenue_monthly'], 0),
  net_subs_weekly: pickNumber(record, ['net_subs_weekly'], 0),
  cannib_pct_of_portfolio: normalizePercentValue(pickNumber(record, ['cannib_pct_of_portfolio'], 0)),
  most_cannibalized_bundle_id: String(getRecordValue(record, ['most_cannibalized_bundle_id']) ?? ''),
  most_cannibalized_bundle_name: pickString(record, ['most_cannibalized_bundle_name'], 'None'),
  most_cannibalized_delta_rev: pickNumber(record, ['most_cannibalized_delta_rev'], 0),
  high_risk_count: pickNumber(record, ['high_risk_count'], 0),
  medium_risk_count: pickNumber(record, ['medium_risk_count'], 0),
  safe_bundle_count: pickNumber(record, ['safe_bundle_count'], 0),
})

const normalizeImpactRow = (record: Record<string, unknown>): GeneratorImpactRow => ({
  new_bundle_id: String(getRecordValue(record, ['new_bundle_id', 'bundle_id', 'generated_bundle_id']) ?? ''),
  new_bundle_type: pickString(record, ['new_bundle_type', 'bundle_type'], 'Unknown'),
  new_price: pickNumber(record, ['new_price', 'price'], 0),
  predicted_popularity: pickNumber(record, ['predicted_popularity', 'popularity_score'], 0),
  existing_bundle_id: String(getRecordValue(record, ['existing_bundle_id']) ?? ''),
  existing_bundle_name: pickString(record, ['existing_bundle_name'], 'Existing bundle'),
  existing_bundle_type: pickString(record, ['existing_bundle_type'], 'Unknown'),
  existing_price: pickNumber(record, ['existing_price'], 0),
  existing_volume_gb: pickNumber(record, ['existing_volume_gb'], 0),
  existing_minutes: pickNumber(record, ['existing_minutes'], 0),
  existing_sms: pickNumber(record, ['existing_sms'], 0),
  existing_avg_rev_weekly: pickNumber(record, ['existing_avg_rev_weekly'], 0),
  existing_avg_subs_weekly: pickNumber(record, ['existing_avg_subs_weekly'], 0),
  similarity: pickNumber(record, ['similarity'], 0),
  cannib_rate: pickNumber(record, ['cannib_rate'], 0),
  cannib_rate_pct: normalizePercentValue(pickNumber(record, ['cannib_rate_pct', 'cannib_rate'], 0)),
  delta_revenue_weekly: pickNumber(record, ['delta_revenue_weekly'], 0),
  delta_revenue_monthly: pickNumber(record, ['delta_revenue_monthly'], 0),
  delta_subs_weekly: pickNumber(record, ['delta_subs_weekly'], 0),
  risk_tier: pickString(record, ['risk_tier'], 'safe'),
})

const normalizeGeneratorResponse = (response: BundleGeneratorApiResponse): GeneratorDashboardState => {
  const summaries = response.summary.map(normalizeSummaryRow)
  const impacts = response.impact_rows.map(normalizeImpactRow)
  const summaryById = new Map(summaries.map((row) => [row.new_bundle_id, row] as const))
  const impactsById = new Map<string, GeneratorImpactRow[]>()

  impacts.forEach((row) => {
    const current = impactsById.get(row.new_bundle_id) ?? []
    current.push(row)
    impactsById.set(row.new_bundle_id, current)
  })

  const bundleViews = response.generated_bundles
    .map((generated) => {
      const id = String(generated.bundle_id)
      return {
        id,
        generated,
        summary: summaryById.get(id) ?? null,
        impacts: (impactsById.get(id) ?? []).slice().sort((left, right) => left.delta_revenue_weekly - right.delta_revenue_weekly),
      }
    })
    .sort((left, right) => (right.summary?.net_revenue_weekly ?? 0) - (left.summary?.net_revenue_weekly ?? 0))

  return {
    request: response.request,
    meta: response.meta,
    modelParams: response.model_params,
    existingBundles: response.existing_bundles.slice().sort((left, right) => right.avg_weekly_revenue - left.avg_weekly_revenue),
    summaries,
    impacts,
    topPerType:
      response.top_per_type.length > 0
        ? response.top_per_type.map(normalizeSummaryRow)
        : summaries.slice(0, response.request.top_n * Math.max(response.request.allowed_bundle_types.length, 1)),
    bundleViews,
  }
}

const buildGeneratorOverviewText = (request: BundleGeneratorRequestPayload) =>
  `${request.offer_type.toUpperCase()} generation across ${request.allowed_bundle_types.length} bundle type${request.allowed_bundle_types.length === 1 ? '' : 's'} with ${request.validity_options.length} validity option${request.validity_options.length === 1 ? '' : 's'}.`

const buildPortfolioChart = (existingBundles: GeneratorExistingBundleItem[]) =>
  existingBundles.slice(0, 8).map((bundle) => ({
    name: bundle.bundle_name,
    revenue: bundle.avg_weekly_revenue,
    subs: bundle.avg_weekly_subs,
  }))

const buildRevenueImpactChart = (summary: GeneratorSummaryRow) => [
  {
    label: 'Incremental',
    value: summary.incremental_revenue_weekly,
    fill: 'url(#generatorRevenueImpactIncremental)',
    note: 'New revenue created',
  },
  {
    label: 'Cannibalization',
    value: -Math.abs(summary.total_cannib_revenue_weekly),
    fill: 'url(#generatorRevenueImpactCannibalization)',
    note: 'Revenue shifted away',
  },
  {
    label: 'Net revenue',
    value: summary.net_revenue_weekly,
    fill: 'url(#generatorRevenueImpactNet)',
    note: 'Net weekly effect',
  },
]

const buildSimilarityChart = (impacts: GeneratorImpactRow[]) =>
  impacts
    .slice()
    .sort((left, right) => right.similarity - left.similarity)
    .slice(0, 6)
    .map((row) => ({
      name: row.existing_bundle_name,
      similarity: roundNumber(normalizePercentValue(row.similarity), 1),
      deltaRevenue: row.delta_revenue_weekly,
      riskTier: row.risk_tier,
    }))

const getBundleTypeColor = (bundleType: string) => {
  switch (bundleType) {
    case 'BUNDLE_DATA':
      return '#14b8a6'
    case 'BUNDLE_VOICE':
      return '#0ea5e9'
    case 'BUNDLE_SMS':
      return '#f59e0b'
    default:
      return '#6366f1'
  }
}

const buildRecommendationMatrixChart = (recommendations: GeneratorBundleView[]) =>
  recommendations
    .map((bundle) => {
      if (!bundle.summary) {
        return null
      }

      const summary = bundle.summary
      const bundleTypeLabel = formatBundleTypeLabel(summary.new_bundle_type)

      return {
        id: bundle.id,
        name: `${bundleTypeLabel} - Fr ${wholeNumber.format(summary.new_price)}`,
        shortLabel: `${bundleTypeLabel.split(' ').slice(-1)[0] ?? bundleTypeLabel} ${wholeNumber.format(summary.new_price)}`,
        netRevenue: summary.net_revenue_weekly,
        portfolioRisk: roundNumber(summary.cannib_pct_of_portfolio, 1),
        popularity: roundNumber(summary.predicted_popularity, 1),
        price: summary.new_price,
        bundleTypeLabel,
        fill: getBundleTypeColor(summary.new_bundle_type),
      }
    })
    .filter((row): row is NonNullable<typeof row> => Boolean(row))

const buildBundleDesignChart = (recommendations: GeneratorBundleView[]) =>
  recommendations
    .map((bundle) => {
      if (!bundle.summary) {
        return null
      }

      const summary = bundle.summary
      const bundleTypeLabel = formatBundleTypeLabel(summary.new_bundle_type)

      return {
        id: bundle.id,
        name: `${bundleTypeLabel} ${wholeNumber.format(summary.new_price)}`,
        shortLabel: `${bundleTypeLabel.split(' ').slice(-1)[0] ?? bundleTypeLabel} ${wholeNumber.format(summary.new_price)}`,
        price: summary.new_price,
        popularity: roundNumber(summary.predicted_popularity, 1),
        netRevenue: summary.net_revenue_weekly,
        bundleTypeLabel,
        validityLabel: formatValidityLabel(summary.new_validity_days, summary.new_validity_days * 24, summary.new_validity_bucket),
        dataGb: roundNumber(summary.new_volume_mb / 1024, 1),
        minutes: summary.new_volume_min,
        sms: summary.new_volume_sms,
        color: getBundleTypeColor(summary.new_bundle_type),
      }
    })
    .filter((row): row is NonNullable<typeof row> => Boolean(row))

const SectionHeading = ({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string
  title: string
  description: string
}) => (
  <div>
    <p className="text-xs font-semibold uppercase tracking-[0.38em] text-minteal-400">{eyebrow}</p>
    <h2 className="mt-2 text-2xl font-semibold text-minteal-950">{title}</h2>
    <p className="mt-2 max-w-3xl text-sm leading-7 text-minteal-600">{description}</p>
  </div>
)

const SelectField = ({
  label,
  hint,
  value,
  options,
  disabled,
  onChange,
}: {
  label: string
  hint: string
  value: string
  options: SelectOption[]
  disabled?: boolean
  onChange: (value: string) => void
}) => (
  <label className="block">
    <span className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">{label}</span>
    <select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} className={fieldInputClassName}>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
    <p className="mt-2 text-xs leading-6 text-minteal-500">{hint}</p>
  </label>
)

const MetricTile = ({
  label,
  value,
  helper,
  caption,
  tone,
}: {
  label: string
  value: string
  helper: string
  caption: string
  tone: MetricTone
}) => {
  const styles = metricToneStyles[tone]

  return (
    <div className={`${panelClassName} p-5`}>
      <div className="flex items-center justify-between gap-3">
        <span className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.28em] ${styles.labelClassName}`}>
          {label}
        </span>
        <span className={`h-2.5 w-2.5 rounded-full ${styles.accentClassName}`} />
      </div>
      <p className={`mt-5 text-3xl font-semibold ${styles.valueClassName}`}>{value}</p>
      <p className="mt-3 text-sm leading-7 text-minteal-600">{helper}</p>
      <p className="mt-4 text-sm font-semibold text-minteal-500">{caption}</p>
    </div>
  )
}

const formatMbaKeyLabel = (key: string) => {
  switch (key) {
    case 'volume_data_mb':
      return 'Data'
    case 'volume_voice_min':
      return 'Voice'
    case 'volume_sms':
      return 'SMS'
    default:
      return key.replace(/_/g, ' ')
  }
}

const formatMbaComponentValue = (key: string, value: number) => {
  switch (key) {
    case 'volume_data_mb':
      return `${compactNumber.format(value)} MB`
    case 'volume_voice_min':
      return `${compactNumber.format(value)} min`
    case 'volume_sms':
      return `${compactNumber.format(value)} SMS`
    default:
      return compactNumber.format(value)
  }
}

const formatRatioPercent = (value: number) => `${roundNumber(value * 100, 1)}%`

const mbaNodePalette = ['#14b8a6', '#0f766e', '#38bdf8', '#0ea5e9', '#f59e0b', '#fb7185', '#2dd4bf']

const getMbaNodeColor = (name: string) => {
  const codeTotal = name.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return mbaNodePalette[codeTotal % mbaNodePalette.length]
}

const hexToRgb = (hexColor: string) => {
  const normalized = hexColor.replace('#', '')

  if (normalized.length !== 6) {
    return { r: 20, g: 184, b: 166 }
  }

  return {
    r: Number.parseInt(normalized.slice(0, 2), 16),
    g: Number.parseInt(normalized.slice(2, 4), 16),
    b: Number.parseInt(normalized.slice(4, 6), 16),
  }
}

const getMbaNodeTone = (name: string) => {
  const base = getMbaNodeColor(name)
  const { r, g, b } = hexToRgb(base)

  return {
    base,
    soft: `rgba(${r}, ${g}, ${b}, 0.14)`,
    border: `rgba(${r}, ${g}, ${b}, 0.3)`,
    ink: `rgba(${Math.max(r - 34, 12)}, ${Math.max(g - 30, 24)}, ${Math.max(b - 28, 24)}, 1)`,
  }
}

const escapeHtml = (value: string) =>
  value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')

const buildMbaSankeyTooltip = (params: any) => {
  if (params.dataType === 'edge') {
    return [
      '<div style="min-width:240px;border:1px solid #dbe5e5;border-radius:18px;background:rgba(255,255,255,0.98);padding:16px 18px;box-shadow:0 20px 50px -28px rgba(12,27,27,0.32)">',
      '<p style="margin:0;font-size:11px;font-weight:700;letter-spacing:0.24em;text-transform:uppercase;color:#7cb7b4">Relationship</p>',
      `<p style="margin:10px 0 0;font-size:16px;font-weight:700;color:#102a2a">${escapeHtml(String(params.data.source_name ?? params.data.source ?? 'Source'))} &rarr; ${escapeHtml(String(params.data.target_name ?? params.data.target ?? 'Target'))}</p>`,
      '<div style="margin-top:12px;display:grid;gap:8px;font-size:13px;color:#3e6767">',
      `<p style="margin:0">Support: ${formatRatioPercent(Number(params.data.value ?? 0))}</p>`,
      `<p style="margin:0">Confidence: ${formatRatioPercent(Number(params.data.avg_confidence ?? 0))}</p>`,
      `<p style="margin:0">Lift: ${roundNumber(Number(params.data.avg_lift ?? 0), 2)}</p>`,
      `<p style="margin:0">Strength: ${roundNumber(Number(params.data.strength_score ?? 0), 3)}</p>`,
      `<p style="margin:0">Rule count: ${Number(params.data.edge_count ?? 0)}</p>`,
      '</div>',
      '</div>',
    ].join('')
  }

  return [
    '<div style="min-width:220px;border:1px solid #dbe5e5;border-radius:18px;background:rgba(255,255,255,0.98);padding:16px 18px;box-shadow:0 20px 50px -28px rgba(12,27,27,0.32)">',
    '<p style="margin:0;font-size:11px;font-weight:700;letter-spacing:0.24em;text-transform:uppercase;color:#7cb7b4">Component</p>',
    `<p style="margin:10px 0 0;font-size:16px;font-weight:700;color:#102a2a">${escapeHtml(String(params.name ?? 'Node'))}</p>`,
    '<div style="margin-top:12px;display:grid;gap:8px;font-size:13px;color:#3e6767">',
    `<p style="margin:0">Total flow: ${formatRatioPercent(Number(params.value ?? 0))}</p>`,
    `<p style="margin:0">Incoming relationships: ${Array.isArray(params.data?.targetLinks) ? params.data.targetLinks.length : 0}</p>`,
    `<p style="margin:0">Outgoing relationships: ${Array.isArray(params.data?.sourceLinks) ? params.data.sourceLinks.length : 0}</p>`,
    '</div>',
    '</div>',
  ].join('')
}

const buildMbaSankeyOption = (sankey: MbaSankeyResponse): EChartsOption => {
  const nodeTotals = new Map<string, number>()
  const sourceNames = new Set<string>()
  const targetNames = new Set<string>()

  sankey.links.forEach((link) => {
    sourceNames.add(link.source_name)
    targetNames.add(link.target_name)
    nodeTotals.set(link.source_name, (nodeTotals.get(link.source_name) ?? 0) + Number(link.value ?? 0))
    nodeTotals.set(link.target_name, (nodeTotals.get(link.target_name) ?? 0) + Number(link.value ?? 0))
  })

  return {
    animationDuration: 700,
    animationDurationUpdate: 450,
    animationEasing: 'cubicOut',
    animationEasingUpdate: 'cubicOut',
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove',
      enterable: true,
      confine: true,
      backgroundColor: 'transparent',
      borderWidth: 0,
      padding: 0,
      extraCssText: 'box-shadow:none;',
      formatter: (params: any) => buildMbaSankeyTooltip(params),
    },
    series: [
      {
        type: 'sankey',
        left: 28,
        right: 28,
        top: 54,
        bottom: 20,
        draggable: true,
        roam: true,
        nodeAlign: 'justify',
        layoutIterations: 40,
        nodeWidth: 18,
        nodeGap: 24,
        emphasis: {
          focus: 'adjacency',
        },
        itemStyle: {
          borderWidth: 1.5,
          borderColor: 'rgba(255,255,255,0.94)',
        },
        lineStyle: {
          color: 'gradient',
          curveness: 0.5,
          opacity: 0.34,
        },
        label: {
          show: false,
          fontSize: 12,
          fontWeight: 700,
          color: '#163535',
          width: 170,
          overflow: 'truncate',
          backgroundColor: 'rgba(255,255,255,0.94)',
          borderColor: 'rgba(178,233,227,0.95)',
          borderWidth: 1,
          borderRadius: 16,
          padding: [10, 14, 10, 14],
          lineHeight: 18,
          rich: {
            name: {
              fontSize: 12,
              fontWeight: 700,
              color: '#163535',
            },
            meta: {
              fontSize: 10.5,
              fontWeight: 600,
              color: '#4c7c7c',
            },
          },
          formatter: (params: any) =>
            `{name|${String(params.name ?? '')}}\n{meta|${formatRatioPercent(Number(params.value ?? 0))} total flow}`,
        },
        levels: [
          {
            depth: 0,
            itemStyle: {
              color: '#14b8a6',
            },
            lineStyle: {
              opacity: 0.32,
            },
          },
          {
            depth: 1,
            itemStyle: {
              color: '#38bdf8',
            },
            lineStyle: {
              opacity: 0.4,
            },
          },
        ],
        data: sankey.nodes.map((node) => {
          const tone = getMbaNodeTone(node.name)
          const isTargetOnly = targetNames.has(node.name) && !sourceNames.has(node.name)

          return {
            ...node,
            value: nodeTotals.get(node.name) ?? 0,
            draggable: true,
            itemStyle: {
              color: tone.base,
              borderColor: 'rgba(255,255,255,0.94)',
              borderWidth: 1.5,
              shadowBlur: 18,
              shadowColor: tone.soft,
            },
            label: {
              show: false,
              position: isTargetOnly ? 'left' : 'right',
              color: tone.ink,
              borderColor: tone.border,
              align: isTargetOnly ? 'right' : 'left',
            },
          }
        }),
        links: sankey.links.map((link) => ({
          ...link,
          lineStyle: {
            color: 'gradient',
            opacity: clamp(0.24 + Number(link.strength_score ?? 0) * 0.35, 0.24, 0.78),
          },
        })),
      },
    ],
  }
}





const MbaBundleCard = ({ bundle }: { bundle: MbaBundleItem }) => (
  <article className="rounded-[1.8rem] border border-minteal-100 bg-white p-5 shadow-[0_20px_60px_-42px_rgba(12,27,27,0.3)]">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">MBA bundle</p>
        <h3 className="mt-2 text-2xl font-semibold text-minteal-950">{bundle.name}</h3>
      </div>
      <div className="rounded-[1.3rem] border border-minteal-100 bg-minteal-50 px-4 py-3 text-right">
        <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Calculated price</p>
        <p className="mt-2 text-2xl font-semibold text-minteal-950">{formatWholeCurrency(bundle.calculated_price)}</p>
      </div>
    </div>

    <div className="mt-5 grid gap-3 sm:grid-cols-3">
      <div className="rounded-[1.3rem] bg-minteal-50 p-4">
        <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Validity</p>
        <p className="mt-2 text-lg font-semibold text-minteal-950">{bundle.validity_days} day(s)</p>
      </div>
      <div className="rounded-[1.3rem] bg-minteal-50 p-4">
        <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">MBA score</p>
        <p className="mt-2 text-lg font-semibold text-minteal-950">{roundNumber(bundle.score, 2)}</p>
      </div>
      <div className="rounded-[1.3rem] bg-minteal-50 p-4">
        <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Services</p>
        <p className="mt-2 text-lg font-semibold text-minteal-950">{Object.keys(bundle.components).length}</p>
      </div>
    </div>

    <div className="mt-5">
      <p className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">Bundle composition</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {Object.entries(bundle.components).map(([key, value]) => (
          <span
            key={`${bundle.name}-${key}`}
            className="rounded-full border border-minteal-200 bg-minteal-50 px-3 py-2 text-sm font-medium text-minteal-700"
          >
            {formatMbaKeyLabel(key)}: {formatMbaComponentValue(key, value)}
          </span>
        ))}
      </div>
    </div>

    <div className="mt-5 grid gap-3 md:grid-cols-3">
      {Object.entries(bundle.individual_prices).map(([key, value]) => (
        <div key={`${bundle.name}-${key}-price`} className="rounded-[1.2rem] border border-minteal-100 bg-white p-4">
          <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">{formatMbaKeyLabel(key)}</p>
          <p className="mt-2 text-lg font-semibold text-minteal-950">{formatWholeCurrency(value)}</p>
        </div>
      ))}
    </div>

    <div className="mt-5 rounded-[1.4rem] border border-minteal-100 bg-minteal-50/80 px-5 py-4 text-sm leading-7 text-minteal-700">
      {bundle.justification}
    </div>
  </article>
)

const BundleGenerationPage = () => {
  const [generatorForm, setGeneratorForm] = useState<GeneratorFormState>(DEFAULT_GENERATOR_FORM)
  const [isGenerating, setIsGenerating] = useState(false)
  const [stageIndex, setStageIndex] = useState(0)
  const [generatorData, setGeneratorData] = useState<GeneratorDashboardState | null>(null)
  const [selectedBundleId, setSelectedBundleId] = useState<string | null>(null)
  const [generatedAt, setGeneratedAt] = useState<string | null>(null)
  const [generationCount, setGenerationCount] = useState(0)
  const [generationError, setGenerationError] = useState<string | null>(null)
  const [mbaForm, setMbaForm] = useState<MbaFormState>(MBA_DEFAULT_FORM)
  const [mbaBundles, setMbaBundles] = useState<MbaBundleItem[]>([])
  const [mbaSankey, setMbaSankey] = useState<MbaSankeyResponse | null>(null)
  const [mbaLoading, setMbaLoading] = useState(false)
  const [mbaRunCount, setMbaRunCount] = useState(0)
  const [mbaError, setMbaError] = useState<string | null>(null)

  const strongestEdge = useMemo(() => mbaSankey?.edge_table[0] ?? null, [mbaSankey])
  const averageMbaConfidence = useMemo(() => {
    if (!mbaSankey || mbaSankey.edge_table.length === 0) {
      return 0
    }

    return mbaSankey.edge_table.reduce((sum, edge) => sum + edge.avg_confidence, 0) / mbaSankey.edge_table.length
  }, [mbaSankey])
  const mbaSankeyChartOption = useMemo(() => (mbaSankey ? buildMbaSankeyOption(mbaSankey) : null), [mbaSankey])
  const averageMbaPrice = useMemo(() => {
    if (mbaBundles.length === 0) {
      return 0
    }

    return mbaBundles.reduce((sum, bundle) => sum + bundle.calculated_price, 0) / mbaBundles.length
  }, [mbaBundles])

  const selectedBundle = useMemo(
    () =>
      generatorData?.bundleViews.find((bundle) => bundle.id === selectedBundleId) ??
      generatorData?.bundleViews[0] ??
      null,
    [generatorData, selectedBundleId],
  )

  const selectedSummary = selectedBundle?.summary ?? null
  const selectedImpactRows = selectedBundle?.impacts ?? []
  const recommendationViews = useMemo(() => {
    if (!generatorData) {
      return []
    }

    const bundleById = new Map(generatorData.bundleViews.map((bundle) => [bundle.id, bundle] as const))
    return generatorData.topPerType
      .map((row) => bundleById.get(row.new_bundle_id))
      .filter((bundle): bundle is GeneratorBundleView => Boolean(bundle))
  }, [generatorData])
  const activeRecommendationIndex = useMemo(
    () => Math.max(recommendationViews.findIndex((bundle) => bundle.id === selectedBundleId), 0),
    [recommendationViews, selectedBundleId],
  )
  const activeRecommendation = useMemo(
    () => recommendationViews[activeRecommendationIndex] ?? recommendationViews[0] ?? null,
    [activeRecommendationIndex, recommendationViews],
  )
  const portfolioChartData = useMemo(() => buildPortfolioChart(generatorData?.existingBundles ?? []), [generatorData])
  const revenueImpactChartData = useMemo(
    () => (selectedSummary ? buildRevenueImpactChart(selectedSummary) : []),
    [selectedSummary],
  )
  const similarityChartData = useMemo(() => buildSimilarityChart(selectedImpactRows), [selectedImpactRows])
  const similarityChartHeight = useMemo(() => Math.max(320, similarityChartData.length * 58), [similarityChartData])
  const recommendationMatrixData = useMemo(
    () => buildRecommendationMatrixChart(recommendationViews),
    [recommendationViews],
  )
  const bundleDesignChartData = useMemo(() => buildBundleDesignChart(recommendationViews), [recommendationViews])
  const topCannibalizedRows = useMemo(
    () => selectedImpactRows.filter((row) => row.delta_revenue_weekly < 0).slice(0, 3),
    [selectedImpactRows],
  )
  useEffect(() => {
    if (!isGenerating) {
      return undefined
    }

    const stageTimer = window.setInterval(() => {
      setStageIndex((current) => (current < generationStages.length - 1 ? current + 1 : current))
    }, 520)

    return () => {
      window.clearInterval(stageTimer)
    }
  }, [isGenerating])

  useEffect(() => {
    if (!generatorData?.bundleViews.some((bundle) => bundle.id === selectedBundleId)) {
      setSelectedBundleId(generatorData?.bundleViews[0]?.id ?? null)
    }
  }, [generatorData, selectedBundleId])

  const updateGeneratorField = <K extends keyof GeneratorFormState>(field: K, value: GeneratorFormState[K]) => {
    setGeneratorForm((current) => ({ ...current, [field]: value }))
  }

  const toggleBundleType = (bundleType: GeneratorBundleType) => {
    setGeneratorForm((current) => {
      const exists = current.allowedBundleTypes.includes(bundleType)
      const next = exists
        ? current.allowedBundleTypes.filter((item) => item !== bundleType)
        : [...current.allowedBundleTypes, bundleType]

      return {
        ...current,
        allowedBundleTypes: next.length > 0 ? next : current.allowedBundleTypes,
      }
    })
  }

  const toggleValidityOption = (hours: number) => {
    setGeneratorForm((current) => {
      const exists = current.validityOptions.includes(hours)
      const next = exists
        ? current.validityOptions.filter((item) => item !== hours)
        : [...current.validityOptions, hours].sort((left, right) => left - right)

      return {
        ...current,
        validityOptions: next.length > 0 ? next : current.validityOptions,
      }
    })
  }

  const showPreviousRecommendation = () => {
    if (recommendationViews.length === 0) {
      return
    }

    const nextIndex = activeRecommendationIndex === 0 ? recommendationViews.length - 1 : activeRecommendationIndex - 1
    setSelectedBundleId(recommendationViews[nextIndex].id)
  }

  const showNextRecommendation = () => {
    if (recommendationViews.length === 0) {
      return
    }

    const nextIndex = activeRecommendationIndex === recommendationViews.length - 1 ? 0 : activeRecommendationIndex + 1
    setSelectedBundleId(recommendationViews[nextIndex].id)
  }

  const updateMbaField = <K extends keyof MbaFormState>(field: K, value: MbaFormState[K]) => {
    setMbaForm((current) => ({ ...current, [field]: value }))
  }

  const handleGenerate = async () => {
    if (isGenerating) {
      return
    }

    setGenerationError(null)
    setStageIndex(0)
    setIsGenerating(true)

    try {
      const requestBody = buildGeneratorRequest(generatorForm)
      const response = await generateBundles(requestBody)
      const normalized = normalizeGeneratorResponse(response)

      startTransition(() => {
        setGeneratorData(normalized)
        setSelectedBundleId(normalized.topPerType[0]?.new_bundle_id ?? normalized.bundleViews[0]?.id ?? null)
        setGeneratedAt(timeFormatter.format(new Date()))
        setGenerationCount((current) => current + 1)
      })
    } catch (error) {
      setGenerationError(getErrorMessage(error))
    } finally {
      setIsGenerating(false)
    }
  }

  const handleRunMbaAnalysis = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setMbaLoading(true)
    setMbaError(null)
    setMbaRunCount((current) => current + 1)

    try {
      const [bundlesResponse, sankeyResponse] = await Promise.all([
        axios.post<MbaBundlesResponse>(`${API_BASE_URL}/mba/hybrid-bundles`, {
          top_k: parsePositiveInteger(mbaForm.topK, 6),
          allowed_sizes: [2, 3],
          min_freq: parsePositiveInteger(mbaForm.minFreq, 5000),
          min_support_pct: parsePositiveFloat(mbaForm.minSupportPct, 0.001),
          suppress_subsets: true,
          offer_type: mbaForm.offerType,
        }),
        axios.post<MbaSankeyResponse>(`${API_BASE_URL}/mba/item-relationship-sankey`, {
          top_n_edges: parsePositiveInteger(mbaForm.topNEdges, 18),
          split_rule_weight_across_pairs: true,
        }),
      ])

      startTransition(() => {
        setMbaBundles(bundlesResponse.data.bundles ?? [])
        setMbaSankey(sankeyResponse.data)
      })
    } catch (error) {
      setMbaError(getErrorMessage(error))
    } finally {
      setMbaLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-[2.6rem] border border-minteal-900/70 px-6 py-8 text-white shadow-[0_34px_110px_-54px_rgba(8,18,18,0.75)] sm:px-8">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              'radial-gradient(circle at 18% 22%, rgba(45,212,191,0.24), transparent 30%), radial-gradient(circle at 86% 16%, rgba(245,158,11,0.18), transparent 24%), radial-gradient(circle at 76% 78%, rgba(56,189,248,0.16), transparent 24%), linear-gradient(135deg, rgba(12,27,27,1), rgba(8,18,18,0.97))',
          }}
        />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px)] bg-[size:82px_82px] opacity-20" />
        <div className="relative max-w-5xl">
          <p className="text-xs font-semibold uppercase tracking-[0.45em] text-minteal-200">AI Bundle Studio</p>
          <h1 className="mt-4 max-w-4xl text-4xl font-semibold tracking-tight sm:text-[3.6rem] sm:leading-[1.05]">
            AI launch board built for telecom growth.
          </h1>
          <p className="mt-5 max-w-3xl text-sm leading-8 text-white/78 sm:text-base">
            Choose the bundle attributes, run the AI generator, then review the generated bundle recommendations, revenue outlook, and cannibalization charts below.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            <span className="rounded-full border border-white/10 bg-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.24em] text-white/80">
              AI generator
            </span>
            <span className="rounded-full border border-white/10 bg-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.24em] text-white/80">
              MBA
            </span>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
        <div className={`${panelClassName} p-6 sm:p-7`}>
          <div className="flex items-start justify-between gap-4">
            <SectionHeading
              eyebrow="Generator Controls"
              title="Configure bundle generation"
              description="Choose the params, then generate bundle candidates and explore the returned impact analysis."
            />
            <AdjustmentsHorizontalIcon className="h-11 w-11 rounded-2xl bg-minteal-50 p-2.5 text-minteal-700" />
          </div>
          <div className="mt-6 grid gap-5 md:grid-cols-2">
            <SelectField
              label="Offer type"
              hint={priceOptions.find((option) => option.value === generatorForm.offerType)?.hint ?? ''}
              value={generatorForm.offerType}
              options={priceOptions}
              disabled={isGenerating}
              onChange={(value) => updateGeneratorField('offerType', value as OfferType)}
            />
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">Samples per type</span>
              <input type="number" min="1" value={generatorForm.samplesPerType} disabled={isGenerating} onChange={(event) => updateGeneratorField('samplesPerType', event.target.value)} className={fieldInputClassName} />
              <p className="mt-2 text-xs leading-6 text-minteal-500">Higher Value, Deeper Exploration.</p>
            </label>
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">Max MB</span>
              <input type="number" min="1" value={generatorForm.maxVolumeMb} disabled={isGenerating} onChange={(event) => updateGeneratorField('maxVolumeMb', event.target.value)} className={fieldInputClassName} />
              <p className="mt-2 text-xs leading-6 text-minteal-500">Upper bound for generated data allowance.</p>
            </label>
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">Max minutes</span>
              <input type="number" min="1" value={generatorForm.maxVolumeMin} disabled={isGenerating} onChange={(event) => updateGeneratorField('maxVolumeMin', event.target.value)} className={fieldInputClassName} />
              <p className="mt-2 text-xs leading-6 text-minteal-500">Upper bound for generated voice allowance.</p>
            </label>
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">Max SMS</span>
              <input type="number" min="1" value={generatorForm.maxVolumeSms} disabled={isGenerating} onChange={(event) => updateGeneratorField('maxVolumeSms', event.target.value)} className={fieldInputClassName} />
              <p className="mt-2 text-xs leading-6 text-minteal-500">Upper bound for generated SMS allowance.</p>
            </label>
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">Top N</span>
              <input type="number" min="1" value={generatorForm.topN} disabled={isGenerating} onChange={(event) => updateGeneratorField('topN', event.target.value)} className={fieldInputClassName} />
              <p className="mt-2 text-xs leading-6 text-minteal-500">Best recommendations returned per bundle type.</p>
            </label>
          </div>
          <div className="mt-6 rounded-[1.6rem] border border-minteal-100 bg-minteal-50/70 p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">Allowed bundle types</p>
            <div className="mt-4 flex flex-wrap gap-3">
              {generatorBundleTypeOptions.map((option) => {
                const active = generatorForm.allowedBundleTypes.includes(option.value)
                return (
                  <button
                    key={option.value}
                    type="button"
                    disabled={isGenerating}
                    onClick={() => toggleBundleType(option.value)}
                    className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
                      active ? 'border-minteal-900 bg-minteal-900 text-white' : 'border-minteal-200 bg-white text-minteal-700 hover:border-minteal-400'
                    }`}
                  >
                    {option.label}
                  </button>
                )
              })}
            </div>
          </div>
          <div className="mt-5 rounded-[1.6rem] border border-minteal-100 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">Validity options</p>
            <div className="mt-4 flex flex-wrap gap-3">
              {validityOptionsCatalog.map((option) => {
                const active = generatorForm.validityOptions.includes(option.value)
                return (
                  <button
                    key={option.value}
                    type="button"
                    disabled={isGenerating}
                    onClick={() => toggleValidityOption(option.value)}
                    className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
                      active ? 'border-minteal-900 bg-minteal-900 text-white' : 'border-minteal-200 bg-minteal-50 text-minteal-700 hover:border-minteal-400'
                    }`}
                  >
                    {option.label}
                  </button>
                )
              })}
            </div>
          </div>
          <div className="mt-8 flex flex-col gap-4 rounded-[1.8rem] border border-minteal-100 bg-minteal-50/70 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">Generator status</p>
              <p className="mt-2 text-sm text-minteal-700">
                {generatorData
                  ? `Run #${generationCount} returned ${generatorData.meta.generated_count} generated bundles and ${generatorData.meta.top_per_type_count} shortlist picks.`
                  : 'Set the request controls, then generate bundles to populate the dashboard.'}
              </p>
            </div>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={isGenerating}
              className="inline-flex items-center justify-center gap-2 rounded-full border border-minteal-900 bg-minteal-900 px-6 py-3 text-sm font-semibold text-white shadow-[0_24px_48px_-28px_rgba(12,27,27,0.95)] transition hover:bg-minteal-800 disabled:cursor-not-allowed disabled:border-minteal-400 disabled:bg-minteal-400"
            >
              {isGenerating ? <CpuChipIcon className="h-5 w-5 animate-pulse" /> : <SparklesIcon className="h-5 w-5" />}
              {isGenerating ? 'Generating...' : 'Generate bundles'}
            </button>
          </div>
        </div>

        <div className="relative overflow-hidden rounded-[2.6rem] border border-minteal-900/70 bg-minteal-950 p-6 text-white shadow-[0_34px_110px_-54px_rgba(8,18,18,0.75)] sm:p-7">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                'radial-gradient(circle at 18% 22%, rgba(45,212,191,0.24), transparent 30%), radial-gradient(circle at 86% 16%, rgba(245,158,11,0.18), transparent 24%), radial-gradient(circle at 76% 78%, rgba(56,189,248,0.16), transparent 24%), linear-gradient(135deg, rgba(12,27,27,1), rgba(8,18,18,0.97))',
            }}
          />
          <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px)] bg-[size:72px_72px] opacity-20" />
          <div className="relative">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.36em] text-minteal-200">Generator overview</p>
                <h2 className="mt-3 text-3xl font-semibold">
                  {isGenerating
                    ? 'Generating bundle candidates...'
                    : selectedBundle
                      ? `${formatBundleTypeLabel(selectedBundle.generated.bundle_type)} bundle`
                      : 'Bundle dashboard will appear here'}
                </h2>
                <p className="mt-3 text-sm leading-7 text-white/72">
                  {isGenerating
                    ? generationStages[stageIndex]?.detail
                    : generatorData
                      ? buildGeneratorOverviewText(generatorData.request)
                      : 'This panel summarizes the selected generated bundle.'}
                </p>
              </div>
              <div className="rounded-[1.4rem] border border-white/10 bg-white/10 p-3">
                {isGenerating ? <CpuChipIcon className="h-8 w-8 animate-pulse text-teal-300" /> : <RocketLaunchIcon className="h-8 w-8 text-amber-300" />}
              </div>
            </div>
            {isGenerating ? (
              <div className="mt-8">
                <div className="flex items-center gap-2 text-sm text-white/72">
                  <span className="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-teal-300" />
                  <span className="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-cyan-300 [animation-delay:180ms]" />
                  <span className="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-amber-300 [animation-delay:360ms]" />
                  <span className="ml-2">Waiting for generator response...</span>
                </div>
                <div className="mt-6 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-[1.4rem] border border-white/10 bg-white/[0.06] p-4">
                    <div className="h-3 w-20 animate-pulse rounded-full bg-white/15" />
                    <div className="mt-4 h-8 w-24 animate-pulse rounded-full bg-white/10" />
                    <div className="mt-3 h-3 w-32 animate-pulse rounded-full bg-white/10" />
                  </div>
                  <div className="rounded-[1.4rem] border border-white/10 bg-white/[0.06] p-4">
                    <div className="h-3 w-24 animate-pulse rounded-full bg-white/15" />
                    <div className="mt-4 h-8 w-28 animate-pulse rounded-full bg-white/10" />
                    <div className="mt-3 h-3 w-36 animate-pulse rounded-full bg-white/10" />
                  </div>
                  <div className="rounded-[1.4rem] border border-white/10 bg-white/[0.06] p-4">
                    <div className="h-3 w-16 animate-pulse rounded-full bg-white/15" />
                    <div className="mt-4 h-8 w-20 animate-pulse rounded-full bg-white/10" />
                    <div className="mt-3 h-3 w-28 animate-pulse rounded-full bg-white/10" />
                  </div>
                </div>
                <div className="mt-6 h-2 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-teal-300 via-cyan-300 to-amber-300 transition-all duration-500"
                    style={{ width: `${((stageIndex + 1) / generationStages.length) * 100}%` }}
                  />
                </div>
                <div className="mt-6 space-y-3">
                  {generationStages.map((stage, index) => (
                    <div key={stage.title} className={`rounded-[1.3rem] border px-4 py-3 ${index === stageIndex ? 'border-white/25 bg-white/10' : 'border-white/10 bg-white/[0.04]'}`}>
                      <p className="text-xs uppercase tracking-[0.24em] text-white/50">Step {index + 1}</p>
                      <p className="mt-1 text-sm font-semibold">{stage.title}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : selectedBundle ? (
              <div className="mt-8 grid gap-3 sm:grid-cols-2">
                <div className="rounded-[1.4rem] border border-white/10 bg-white/8 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-white/50">Price</p>
                  <p className="mt-2 text-2xl font-semibold">{formatWholeCurrency(selectedBundle.generated.price)}</p>
                  <p className="mt-2 text-sm text-white/65">{formatValidityLabel(selectedBundle.generated.validity_days, selectedBundle.generated.validity_hours, selectedBundle.generated.validity_bucket)}</p>
                </div>
                <div className="rounded-[1.4rem] border border-white/10 bg-white/8 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-white/50">Volumes</p>
                  <p className="mt-2 text-sm leading-7 text-white/80">
                    {compactNumber.format(selectedBundle.generated.volume_mb)} MB, {compactNumber.format(selectedBundle.generated.volume_min)} min, {compactNumber.format(selectedBundle.generated.volume_sms)} SMS
                  </p>
                  <p className="mt-2 text-sm text-white/65">{selectedBundle.generated.popularity_category ?? 'Unclassified'}</p>
                </div>
                <div className="rounded-[1.4rem] border border-white/10 bg-white/8 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-white/50">Net weekly</p>
                  <p className="mt-2 text-2xl font-semibold">{formatCompactCurrency(selectedSummary?.net_revenue_weekly ?? 0)}</p>
                  <p className="mt-2 text-sm text-white/65">{selectedImpactRows.length} impact rows</p>
                </div>
                <div className="rounded-[1.4rem] border border-white/10 bg-white/8 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-white/50">Generated at</p>
                  <p className="mt-2 text-2xl font-semibold">{generatedAt ?? '--'}</p>
                  <p className="mt-2 text-sm text-white/65">Run #{generationCount}</p>
                </div>
              </div>
            ) : (
              <div className="mt-8 rounded-[1.7rem] border border-white/10 bg-white/[0.06] p-5">
                <p className="text-xs uppercase tracking-[0.25em] text-white/50">Generator request</p>
                <p className="mt-3 text-sm leading-8 text-white/76">
                  Offer type: {generatorForm.offerType}. Allowed bundle types: {generatorForm.allowedBundleTypes.join(', ')}. Validity options: {generatorForm.validityOptions.join(', ')} hours.
                </p>
              </div>
            )}
            {generatorData && !isGenerating ? (
              <div className="mt-8">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-200">Shortlist picks</p>
                  {recommendationViews.length > 0 ? (
                    <div className="flex items-center gap-3">
                      <p className="text-xs uppercase tracking-[0.22em] text-white/45">
                        {activeRecommendationIndex + 1} / {recommendationViews.length}
                      </p>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={showPreviousRecommendation}
                          className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/[0.06] text-white transition hover:border-white/25 hover:bg-white/[0.1]"
                          aria-label="Show previous top bundle"
                        >
                          <ChevronLeftIcon className="h-5 w-5" />
                        </button>
                        <button
                          type="button"
                          onClick={showNextRecommendation}
                          className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/[0.06] text-white transition hover:border-white/25 hover:bg-white/[0.1]"
                          aria-label="Show next top bundle"
                        >
                          <ChevronRightIcon className="h-5 w-5" />
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
                <div className="mt-4 overflow-hidden">
                  {activeRecommendation ? (
                    <button
                      key={`top-${activeRecommendation.id}`}
                      type="button"
                      onClick={() => setSelectedBundleId(activeRecommendation.id)}
                      className="w-full rounded-[1.7rem] border border-white/30 bg-white/14 p-5 text-left text-white transition"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-100">
                            {formatBundleTypeLabel(activeRecommendation.generated.bundle_type)}
                          </p>
                          <p className="mt-3 text-2xl font-semibold">{formatWholeCurrency(activeRecommendation.generated.price)}</p>
                        </div>
                        <span className="rounded-full border border-white/10 bg-white/[0.06] px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-white/72">
                          Bundle {activeRecommendation.id}
                        </span>
                      </div>
                      <p className="mt-4 text-sm leading-7 text-white/72">
                        {compactNumber.format(activeRecommendation.generated.volume_mb)} MB, {compactNumber.format(activeRecommendation.generated.volume_min)} min, {compactNumber.format(activeRecommendation.generated.volume_sms)} SMS
                      </p>
                      <div className="mt-4 grid gap-3 sm:grid-cols-3">
                        <div className="rounded-[1.2rem] border border-white/10 bg-white/[0.05] p-4">
                          <p className="text-xs uppercase tracking-[0.22em] text-white/45">Net weekly</p>
                          <p className="mt-2 text-lg font-semibold text-white/92">{formatCompactCurrency(activeRecommendation.summary?.net_revenue_weekly ?? 0)}</p>
                        </div>
                        <div className="rounded-[1.2rem] border border-white/10 bg-white/[0.05] p-4">
                          <p className="text-xs uppercase tracking-[0.22em] text-white/45">Validity</p>
                          <p className="mt-2 text-sm font-semibold text-white/82">
                            {formatValidityLabel(
                              activeRecommendation.generated.validity_days,
                              activeRecommendation.generated.validity_hours,
                              activeRecommendation.generated.validity_bucket,
                            )}
                          </p>
                        </div>
                        <div className="rounded-[1.2rem] border border-white/10 bg-white/[0.05] p-4">
                          <p className="text-xs uppercase tracking-[0.22em] text-white/45">Popularity</p>
                          <p className="mt-2 text-sm font-semibold text-white/82">
                            {activeRecommendation.generated.popularity_category ?? 'Unclassified'}
                          </p>
                        </div>
                      </div>
                    </button>
                  ) : (
                    <div className="w-full rounded-[1.7rem] border border-white/10 bg-white/[0.06] px-5 py-4 text-sm text-white/70">
                      No shortlist returned by the backend.
                    </div>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </section>

      {generationError ? (
        <section>
          <ErrorState message={generationError} />
        </section>
      ) : null}

      {!generatorData && !isGenerating && !generationError ? (
        <section>
          <EmptyState message="No generated bundles yet. Run the generator to load recommendations, impact rows, KPIs, and portfolio charts." />
        </section>
      ) : null}

      {generatorData && selectedBundle && selectedSummary ? (
        <>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricTile
              label="Incremental weekly"
              value={formatCompactCurrency(selectedSummary.incremental_revenue_weekly)}
              helper="Projected new weekly revenue contributed by the selected generated bundle."
              caption={`${compactNumber.format(selectedSummary.incremental_subs_weekly)} incremental subscribers weekly.`}
              tone="mint"
            />
            <MetricTile
              label="Cannibalization"
              value={formatCompactCurrency(selectedSummary.total_cannib_revenue_weekly)}
              helper="Total weekly revenue at risk across the existing portfolio."
              caption={`${compactNumber.format(selectedSummary.total_cannib_subs_weekly)} subscribers shifted from current bundles.`}
              tone="rose"
            />
            <MetricTile
              label="Net weekly"
              value={formatCompactCurrency(selectedSummary.net_revenue_weekly)}
              helper="Net weekly revenue after cannibalization is applied."
              caption={`${formatCompactCurrency(selectedSummary.net_revenue_monthly)} monthly net revenue.`}
              tone="sky"
            />
            <MetricTile
              label="Net subscriber change"
              value={compactNumber.format(selectedSummary.net_subs_weekly)}
              helper="Net weekly subscriber movement tied to the selected generated bundle."
              caption={`${roundNumber(selectedSummary.cannib_pct_of_portfolio, 1)}% cannibalization across the portfolio.`}
              tone="gold"
            />
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.25fr,0.75fr]">
            <div className={`${panelClassName} p-6 sm:p-7`}>
              <div className="flex items-start justify-between gap-4">
                <SectionHeading
                  eyebrow="Revenue Impact"
                  title="Incremental, cannibalization, and net revenue"
                  description="This chart combines the selected summary row with the most negative impact rows so business users can see the main commercial tradeoffs."
                />
                <ArrowTrendingUpIcon className="h-11 w-11 rounded-2xl bg-minteal-50 p-2.5 text-minteal-700" />
              </div>
              <div className="mt-6 rounded-[1.8rem] border border-minteal-100 bg-[radial-gradient(circle_at_top_left,rgba(20,184,166,0.16),transparent_28%),radial-gradient(circle_at_top_right,rgba(56,189,248,0.14),transparent_28%),linear-gradient(180deg,rgba(255,255,255,1),rgba(241,250,249,0.96))] p-5">
                <div className="flex flex-wrap gap-3">
                  {revenueImpactChartData.map((item) => (
                    <div key={item.label} className="rounded-full border border-white/70 bg-white/80 px-4 py-2 backdrop-blur">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-minteal-400">{item.label}</p>
                      <p className="mt-1 text-sm font-semibold text-minteal-950">{item.note}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-4 h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={revenueImpactChartData} margin={{ top: 12, right: 8, left: 8, bottom: 4 }}>
                      <defs>
                        <linearGradient id="generatorRevenueImpactIncremental" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#2dd4bf" />
                          <stop offset="100%" stopColor="#0f766e" />
                        </linearGradient>
                        <linearGradient id="generatorRevenueImpactCannibalization" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#fb7185" />
                          <stop offset="100%" stopColor="#e11d48" />
                        </linearGradient>
                        <linearGradient id="generatorRevenueImpactNet" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#38bdf8" />
                          <stop offset="100%" stopColor="#2563eb" />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="4 6" vertical={false} stroke={chartGrid} />
                      <XAxis
                        dataKey="label"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: chartText, fontSize: 12 }}
                      />
                      <YAxis
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: chartText, fontSize: 12 }}
                        tickFormatter={(value: number) => `Fr ${compactNumber.format(value)}`}
                      />
                      <ReferenceLine y={0} stroke="#0f172a" strokeOpacity={0.18} />
                      <Tooltip
                        contentStyle={tooltipStyle}
                        formatter={(value: number | string | undefined) => [formatWholeCurrency(Number(value ?? 0)), 'Weekly revenue']}
                        labelFormatter={(label) => `${label}`}
                      />
                      <Bar dataKey="value" radius={[18, 18, 18, 18]} barSize={54} isAnimationActive={false}>
                        {revenueImpactChartData.map((item) => (
                          <Cell key={item.label} fill={item.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            <div className="grid gap-6">
              <div className={`${panelClassName} p-6`}>
                <div className="flex items-start justify-between gap-4">
                  <SectionHeading
                    eyebrow="Commercial Signals"
                    title="Selected bundle commercial summary"
                    description="These values come directly from the selected generated bundle and its matching backend summary row."
                  />
                  <ShieldCheckIcon className="h-11 w-11 rounded-2xl bg-minteal-50 p-2.5 text-minteal-700" />
                </div>
                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[1.2rem] bg-minteal-50 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Monthly net revenue</p>
                    <p className="mt-2 text-lg font-semibold text-minteal-950">{formatCompactCurrency(selectedSummary.net_revenue_monthly)}</p>
                  </div>
                  <div className="rounded-[1.2rem] bg-minteal-50 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Predicted popularity</p>
                    <p className="mt-2 text-lg font-semibold text-minteal-950">{roundNumber(selectedSummary.predicted_popularity, 1)}</p>
                  </div>
                  <div className="rounded-[1.2rem] bg-minteal-50 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Most cannibalized</p>
                    <p className="mt-2 text-sm font-semibold text-minteal-950">{selectedSummary.most_cannibalized_bundle_name || 'No single driver returned'}</p>
                  </div>
                  <div className="rounded-[1.2rem] bg-minteal-50 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Risk mix</p>
                    <p className="mt-2 text-sm font-semibold text-minteal-950">
                      {selectedSummary.high_risk_count} high, {selectedSummary.medium_risk_count} medium, {selectedSummary.safe_bundle_count} safe
                    </p>
                  </div>
                </div>
                <div className="mt-5 rounded-[1.4rem] border border-minteal-100 bg-white p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Commercial narrative</p>
                  <p className="mt-3 text-sm leading-7 text-minteal-700">
                    {'Generated bundle'} is expected to add {compactNumber.format(selectedSummary.incremental_subs_weekly)} weekly subscribers while exposing {roundNumber(selectedSummary.cannib_pct_of_portfolio, 1)}% of portfolio revenue to cannibalization.
                  </p>
                </div>
              </div>
            </div>
          </section>
          <section className="grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
            <div className="grid gap-6">
              <div className={`${panelClassName} p-6 sm:p-7`}>
                <div className="flex items-start justify-between gap-4">
                  <SectionHeading
                    eyebrow="Similarity"
                    title="Most similar existing bundles"
                    description=""
                  />
                  <BoltIcon className="h-11 w-11 rounded-2xl bg-minteal-50 p-2.5 text-minteal-700" />
                </div>
                <div className="mt-6" style={{ height: similarityChartHeight }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={similarityChartData}
                      layout="vertical"
                      margin={{ top: 4, right: 8, left: 24, bottom: 0 }}
                      barCategoryGap="30%"
                    >
                      <CartesianGrid strokeDasharray="4 4" horizontal={false} stroke={chartGrid} />
                      <XAxis
                        type="number"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: chartText, fontSize: 12 }}
                        tickFormatter={(value: number) => `${value}%`}
                      />
                      <YAxis
                        dataKey="name"
                        type="category"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: chartText, fontSize: 12 }}
                        width={170}
                        interval={0}
                      />
                      <Tooltip
                        contentStyle={tooltipStyle}
                        formatter={(value: number | string | undefined, name: string | number | undefined, item) => {
                          if (name === 'similarity') {
                            return [`${Number(value ?? 0)}%`, 'Similarity']
                          }

                          return [formatWholeCurrency(Number(item?.payload?.deltaRevenue ?? 0)), 'Delta revenue weekly']
                        }}
                      />
                      <Bar dataKey="similarity" radius={[0, 12, 12, 0]} barSize={18} isAnimationActive={false}>
                        {similarityChartData.map((entry) => (
                          <Cell key={entry.name} fill={getRiskTierColor(entry.riskTier)} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className={`${panelClassName} p-6`}>
                <div className="flex items-start justify-between gap-4">
                  <SectionHeading
                    eyebrow="Recommendation Matrix"
                    title="Opportunity vs portfolio risk"
                    description="This study view helps marketing compare the strongest generated bundles by net weekly revenue, predicted popularity, and cannibalization pressure."
                  />
                  <RocketLaunchIcon className="h-11 w-11 rounded-2xl bg-minteal-50 p-2.5 text-minteal-700" />
                </div>
                <div className="mt-5 h-[320px] rounded-[1.8rem] border border-minteal-100 bg-[radial-gradient(circle_at_top_left,rgba(45,212,191,0.16),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(14,165,233,0.14),transparent_32%),linear-gradient(180deg,rgba(255,255,255,1),rgba(242,252,251,0.96))] p-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 12, right: 10, left: 4, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="4 6" stroke={chartGrid} />
                      <XAxis
                        type="number"
                        dataKey="portfolioRisk"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: chartText, fontSize: 12 }}
                        tickFormatter={(value: number) => `${value}%`}
                        name="Portfolio risk"
                      />
                      <YAxis
                        type="number"
                        dataKey="netRevenue"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: chartText, fontSize: 12 }}
                        tickFormatter={(value: number) => `Fr ${compactNumber.format(value)}`}
                        name="Net weekly revenue"
                      />
                      <ZAxis type="number" dataKey="popularity" range={[160, 520]} name="Predicted popularity" />
                      <Tooltip
                        cursor={{ strokeDasharray: '4 4' }}
                        contentStyle={tooltipStyle}
                        formatter={(value: number | string | undefined, name: string | number | undefined, item) => {
                          if (name === 'Portfolio risk') {
                            return [`${Number(value ?? 0)}%`, 'Portfolio risk']
                          }
                          if (name === 'Net weekly revenue') {
                            return [formatWholeCurrency(Number(value ?? 0)), 'Net weekly revenue']
                          }
                          return [roundNumber(Number(item?.payload?.popularity ?? 0), 1), 'Predicted popularity']
                        }}
                        labelFormatter={(_, payload) => payload?.[0]?.payload?.name ?? 'Recommendation'}
                      />
                      <Scatter data={recommendationMatrixData} isAnimationActive={false}>
                        {recommendationMatrixData.map((point) => (
                          <Cell key={point.id} fill={point.fill} fillOpacity={0.9} />
                        ))}
                      </Scatter>
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  {recommendationMatrixData.map((point) => (
                    <div key={`${point.id}-legend`} className="rounded-full border border-minteal-100 bg-white px-4 py-2 text-xs font-semibold text-minteal-700">
                      <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ backgroundColor: point.fill }} />
                      {point.shortLabel}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className={`${panelClassName} p-6`}>
              <div className="flex items-start justify-between gap-4">
                <SectionHeading
                  eyebrow="Safeguards"
                  title="Top cannibalization exposures"
                  description="These cards summarize the most negative weekly revenue impacts from the selected generated bundle."
                />
                <MegaphoneIcon className="h-11 w-11 rounded-2xl bg-minteal-50 p-2.5 text-minteal-700" />
              </div>
              <div className="mt-5 space-y-4">
                {topCannibalizedRows.length > 0 ? (
                  topCannibalizedRows.map((row) => (
                    <div key={row.existing_bundle_id} className="rounded-[1.6rem] border border-minteal-100 bg-white p-5">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-lg font-semibold text-minteal-950">{row.existing_bundle_name}</p>
                          <p className="mt-2 text-sm leading-7 text-minteal-600">
                            {formatBundleTypeLabel(row.existing_bundle_type)} shows {roundNumber(normalizePercentValue(row.similarity), 1)}% similarity and {roundNumber(row.cannib_rate_pct, 1)}% cannibalization rate.
                          </p>
                        </div>
                        <div className="rounded-[1.1rem] bg-rose-50 px-3 py-2 text-right">
                          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-rose-500">Delta rev</p>
                          <p className="mt-1 text-xl font-semibold text-rose-700">{formatCompactCurrency(row.delta_revenue_weekly)}</p>
                        </div>
                      </div>
                      <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <div className="rounded-[1.2rem] bg-minteal-50 p-4">
                          <p className="text-xs uppercase tracking-[0.25em] text-minteal-400">Avg weekly revenue</p>
                          <p className="mt-2 text-lg font-semibold text-minteal-950">{formatCompactCurrency(row.existing_avg_rev_weekly)}</p>
                        </div>
                        <div className="rounded-[1.2rem] bg-minteal-50 p-4">
                          <p className="text-xs uppercase tracking-[0.25em] text-minteal-400">Risk tier</p>
                          <p className="mt-2 text-sm font-semibold" style={{ color: getRiskTierColor(row.risk_tier) }}>
                            {formatRiskTierLabel(row.risk_tier)}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <EmptyState message="No negative cannibalization rows are available for the selected generated bundle." />
                )}
              </div>
              <div className="mt-6 rounded-[1.8rem] bg-minteal-950 p-5 text-white">
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-white/55">Current selection</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[1.2rem] bg-white/8 px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.22em] text-white/50">Usage type</p>
                    <p className="mt-2 text-sm font-semibold text-white/80">{selectedBundle.generated.usage_type ?? 'Not provided'}</p>
                  </div>
                  <div className="rounded-[1.2rem] bg-white/8 px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.22em] text-white/50">Service class</p>
                    <p className="mt-2 text-sm font-semibold text-white/80">{selectedBundle.generated.service_class_category ?? 'Not provided'}</p>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </>
      ) : null}

      {generatorData && selectedBundle ? (
        <>
          <section className="grid gap-6 xl:grid-cols-2">
            <div className={`${panelClassName} p-6`}>
              <div className="flex items-start justify-between gap-4">
                <SectionHeading
                  eyebrow="Portfolio"
                  title="Existing portfolio revenue view"
                  description="This chart highlights the highest weekly revenue bundles already in market."
                />
                <ChartBarIcon className="h-11 w-11 rounded-2xl bg-minteal-50 p-2.5 text-minteal-700" />
              </div>
              <div className="mt-5 h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={portfolioChartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="4 4" vertical={false} stroke={chartGrid} />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: chartText, fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={70} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: chartText, fontSize: 12 }} tickFormatter={(value: number) => `Fr ${compactNumber.format(value)}`} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value: number | string | undefined) => [formatWholeCurrency(Number(value ?? 0)), 'Avg weekly revenue']} />
                    <Bar dataKey="revenue" fill={chartMintDark} radius={[12, 12, 0, 0]} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className={`${panelClassName} p-6`}>
              <div className="flex items-start justify-between gap-4">
                <SectionHeading
                  eyebrow="Bundle Design"
                  title="Recommended bundle ranking"
                  description="This chart helps marketing compare the strongest bundle candidates by weekly net revenue before selecting the launch option."
                />
                <UserGroupIcon className="h-11 w-11 rounded-2xl bg-minteal-50 p-2.5 text-minteal-700" />
              </div>
              <div className="mt-5 h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={bundleDesignChartData}
                    layout="vertical"
                    margin={{ top: 8, right: 12, left: 18, bottom: 0 }}
                    barCategoryGap="22%"
                  >
                    <CartesianGrid strokeDasharray="4 4" horizontal={false} stroke={chartGrid} />
                    <XAxis
                      type="number"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: chartText, fontSize: 12 }}
                      tickFormatter={(value: number) => `Fr ${compactNumber.format(value)}`}
                    />
                    <YAxis
                      dataKey="shortLabel"
                      type="category"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: chartText, fontSize: 12 }}
                      width={92}
                      interval={0}
                    />
                    <ReferenceLine x={0} stroke="#94a3b8" strokeDasharray="4 4" />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      formatter={(value: number | string | undefined, _name: string | number | undefined, item) => {
                        const point = item?.payload as (typeof bundleDesignChartData)[number] | undefined

                        if (!point) {
                          return [String(value ?? ''), 'Weekly net revenue']
                        }

                        return [formatWholeCurrency(Number(value ?? 0)), 'Weekly net revenue']
                      }}
                      labelFormatter={(_, payload) => {
                        const point = payload?.[0]?.payload as (typeof bundleDesignChartData)[number] | undefined
                        return point
                          ? `${point.bundleTypeLabel} • ${formatWholeCurrency(point.price)} • ${point.validityLabel} • ${point.dataGb} GB • ${wholeNumber.format(point.minutes)} min • ${wholeNumber.format(point.sms)} SMS • popularity ${roundNumber(point.popularity, 1)}`
                          : 'Bundle candidate'
                      }}
                    />
                    <Bar dataKey="netRevenue" radius={[0, 14, 14, 0]} barSize={22} isAnimationActive={false}>
                      {bundleDesignChartData.map((point) => (
                        <Cell key={point.id} fill={point.color} fillOpacity={0.92} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
             
              </div>
            </div>
          </section>

        </>
      ) : null}

      <section className={`${panelClassName} overflow-hidden`}>
        <div className="relative overflow-hidden border-b border-minteal-900/70 px-6 py-8 text-white sm:px-8">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                'radial-gradient(circle at 18% 22%, rgba(45,212,191,0.24), transparent 30%), radial-gradient(circle at 86% 16%, rgba(245,158,11,0.18), transparent 24%), radial-gradient(circle at 76% 78%, rgba(56,189,248,0.16), transparent 24%), linear-gradient(135deg, rgba(12,27,27,1), rgba(8,18,18,0.97))',
            }}
          />
          <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px)] bg-[size:82px_82px] opacity-20" />
          <div className="relative flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-[0.42em] text-minteal-200">MBA Result</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-[2.5rem]">
                Market Basket Analysis bundles.
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-8 text-white/72">
                This section shows the telecom bundles generated from the most purchased-together items, plus the strongest service relationships.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-[1.4rem] border border-white/10 bg-white/[0.06] px-4 py-4">
                <p className="text-xs uppercase tracking-[0.24em] text-white/45">Bundles found</p>
                <p className="mt-2 text-2xl font-semibold text-white">{mbaBundles.length}</p>
              </div>
              <div className="rounded-[1.4rem] border border-white/10 bg-white/[0.06] px-4 py-4">
                <p className="text-xs uppercase tracking-[0.24em] text-white/45">Avg. price</p>
                <p className="mt-2 text-2xl font-semibold text-white">
                  {mbaBundles.length > 0 ? formatWholeCurrency(averageMbaPrice) : '--'}
                </p>
              </div>
              <div className="rounded-[1.4rem] border border-white/10 bg-white/[0.06] px-4 py-4">
                <p className="text-xs uppercase tracking-[0.24em] text-white/45">Top relationship</p>
                <p className="mt-2 text-base font-semibold text-white">
                  {strongestEdge ? `${strongestEdge.source} -> ${strongestEdge.target}` : 'Waiting for data'}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="p-6 sm:p-8">
          <form onSubmit={handleRunMbaAnalysis}>
            <div className="rounded-[1.9rem] border border-minteal-100 bg-minteal-50/70 p-5">
              <div className="flex items-start justify-between gap-4">
                <SectionHeading
                  eyebrow="MBA Controls"
                  title="Tune the market basket run"
                  description="These fields map directly for hybrid bundles and Sankey relationship output."
                />
                <CubeTransparentIcon className="h-11 w-11 rounded-2xl bg-white p-2.5 text-minteal-700 shadow-sm" />
              </div>

              <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                <label className="block">
                  <span className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">Top bundles</span>
                  <input
                    type="number"
                    min="1"
                    value={mbaForm.topK}
                    onChange={(event) => updateMbaField('topK', event.target.value)}
                    className={mbaInputClassName}
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">Min frequency</span>
                  <input
                    type="number"
                    min="1"
                    value={mbaForm.minFreq}
                    onChange={(event) => updateMbaField('minFreq', event.target.value)}
                    className={mbaInputClassName}
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">Min support %</span>
                  <input
                    type="number"
                    min="0.0001"
                    step="0.0001"
                    value={mbaForm.minSupportPct}
                    onChange={(event) => updateMbaField('minSupportPct', event.target.value)}
                    className={mbaInputClassName}
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-semibold uppercase tracking-[0.28em] text-minteal-400">Top Sankey edges</span>
                  <input
                    type="number"
                    min="1"
                    value={mbaForm.topNEdges}
                    onChange={(event) => updateMbaField('topNEdges', event.target.value)}
                    className={mbaInputClassName}
                  />
                </label>
                <div className="md:col-span-2 xl:col-span-1">
                  <SelectField
                    label="Offer type"
                    hint={priceOptions.find((option) => option.value === mbaForm.offerType)?.hint ?? ''}
                    value={mbaForm.offerType}
                    options={priceOptions}
                    disabled={mbaLoading}
                    onChange={(value) => updateMbaField('offerType', value as OfferType)}
                  />
                </div>
              </div>
              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="submit"
                  disabled={mbaLoading}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-minteal-900 bg-minteal-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-minteal-800 disabled:cursor-not-allowed disabled:border-minteal-400 disabled:bg-minteal-400"
                >
                  {mbaLoading ? (
                    <CpuChipIcon key={`mba-loading-${mbaRunCount}`} className="h-5 w-5 animate-pulse" />
                  ) : (
                    <SparklesIcon className="h-5 w-5" />
                  )}
                  {mbaLoading ? 'Running MBA...' : 'Run MBA analysis'}
                </button>
                <button
                  type="button"
                  disabled={mbaLoading}
                  onClick={() => setMbaForm(MBA_DEFAULT_FORM)}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-minteal-200 bg-white px-5 py-3 text-sm font-semibold text-minteal-700 transition hover:border-minteal-400 hover:bg-minteal-50 disabled:cursor-not-allowed"
                >
                  <ArrowPathIcon className="h-5 w-5" />
                  Reset MBA inputs
                </button>
              </div>
            </div>
          </form>

          {mbaError ? (
            <div className="mt-6">
              <ErrorState message={mbaError} />
            </div>
          ) : null}

          {mbaLoading ? (
            <div className="mt-6 rounded-[1.6rem] border border-minteal-100 bg-minteal-50/80 px-5 py-4">
              <div className="flex items-center gap-3 text-sm font-medium text-minteal-800">
                <span className="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-minteal-500" />
                <span className="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-cyan-300 [animation-delay:180ms]" />
                <span className="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-amber-300 [animation-delay:360ms]" />
                 MBA bundles and relationship chart...
              </div>
            </div>
          ) : null}

          {mbaLoading && mbaBundles.length === 0 && !mbaSankey ? (
            <div className="mt-6">
              <LoadingState message="Running Market Basket Analysis from FastAPI..." />
            </div>
          ) : null}

          {!mbaLoading && mbaBundles.length === 0 && (!mbaSankey || mbaSankey.edge_table.length === 0) && !mbaError ? (
            <div className="mt-6">
              <EmptyState message="No MBA results returned yet." />
            </div>
          ) : null}

          {mbaBundles.length > 0 ? (
            <section className="mt-8">
              <div className="flex items-start justify-between gap-4">
                <SectionHeading
                  eyebrow="Generated Bundles"
                  title="Telecom bundles suggested by MBA"
                  description="These are bundle candidates based on the most purchased-together patterns."
                />
                <RocketLaunchIcon className="hidden h-11 w-11 rounded-2xl bg-minteal-50 p-2.5 text-minteal-700 sm:block" />
              </div>
              <div className="mt-6 grid gap-5 xl:grid-cols-2">
                {mbaBundles.map((bundle) => (
                  <MbaBundleCard key={`${bundle.name}-${bundle.validity_days}`} bundle={bundle} />
                ))}
              </div>
            </section>
          ) : null}

          {mbaSankey && mbaSankey.nodes.length > 0 && mbaSankey.links.length > 0 ? (
            <>
              <section className="mt-8">
                <div className={`${panelClassName} p-6 sm:p-7`}>
                  <div className="flex items-start justify-between gap-4">
                    <SectionHeading
                      eyebrow="Item Relationships"
                      title="Most purchased-together flow"
                      description="this highlights the strongest product-to-product movement across the MBA rules."
                    />
                    <BoltIcon className="h-11 w-11 rounded-2xl bg-minteal-50 p-2.5 text-minteal-700" />
                  </div>

                  <div className="mt-6 rounded-[1.8rem] border border-minteal-100 bg-[radial-gradient(circle_at_top_left,rgba(45,212,191,0.16),transparent_28%),radial-gradient(circle_at_top_right,rgba(56,189,248,0.16),transparent_26%),linear-gradient(180deg,rgba(255,255,255,1),rgba(244,252,251,0.94))] p-5">
                    <div className="grid gap-3 lg:grid-cols-[1.35fr,repeat(3,minmax(0,0.9fr))]">
                      <div className="rounded-[1.35rem] border border-white/70 bg-white/82 px-4 py-4 backdrop-blur">
                        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-minteal-400">How to read</p>
                        <p className="mt-2 text-sm leading-7 text-minteal-800">
                          Drag nodes to reorganize the view, or pan the chart to inspect dense areas. Thicker bands indicate
                          stronger support, and hover shows support, confidence, lift, and rule count.
                        </p>
                      </div>
                      <div className="rounded-[1.35rem] border border-white/70 bg-white/80 px-4 py-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-minteal-400">Relationships</p>
                        <p className="mt-2 text-2xl font-semibold text-minteal-950">{mbaSankey.edge_table.length}</p>
                        <p className="mt-1 text-xs leading-6 text-minteal-500">Top associations rendered in this view</p>
                      </div>
                      <div className="rounded-[1.35rem] border border-white/70 bg-white/80 px-4 py-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-minteal-400">Avg confidence</p>
                        <p className="mt-2 text-2xl font-semibold text-minteal-950">{formatRatioPercent(averageMbaConfidence)}</p>
                        <p className="mt-1 text-xs leading-6 text-minteal-500">Mean rule confidence across visible links</p>
                      </div>
                      <div className="rounded-[1.35rem] border border-white/70 bg-white/80 px-4 py-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-minteal-400">Top pair</p>
                        <p className="mt-2 text-base font-semibold text-minteal-950">
                          {strongestEdge ? `${strongestEdge.source} -> ${strongestEdge.target}` : 'Waiting for data'}
                        </p>
                        <p className="mt-1 text-xs leading-6 text-minteal-500">Highest-ranked relationship in the current run</p>
                      </div>
                    </div>

                    <div className="mt-5">
                      <div className="relative h-[620px] overflow-hidden rounded-[1.7rem] border border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(239,253,250,0.72))] px-6 pb-5 pt-12 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
                        <div className="pointer-events-none absolute inset-x-6 top-5 flex items-center justify-between">
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-minteal-400">Source products</p>
                            <p className="mt-1 text-sm font-medium text-minteal-700">Frequently purchased starting items</p>
                          </div>
                          <div className="text-right">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-minteal-400">Target products</p>
                            <p className="mt-1 text-sm font-medium text-minteal-700">Products most often bought with them</p>
                          </div>
                        </div>
                        <div className="absolute inset-0 rounded-[1.7rem] bg-[linear-gradient(rgba(20,184,166,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(20,184,166,0.04)_1px,transparent_1px)] bg-[size:120px_120px] opacity-50" />
                        <div className="pointer-events-none absolute bottom-5 left-6 z-10 rounded-full border border-white/70 bg-white/88 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-minteal-500 shadow-sm">
                          Drag nodes and pan chart
                        </div>
                        <div className="relative h-full">
                          {mbaSankeyChartOption ? (
                            <ReactECharts
                              option={mbaSankeyChartOption}
                              notMerge
                              lazyUpdate
                              style={{ height: '100%', width: '100%' }}
                            />
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              <section className="mt-6 grid gap-6 xl:grid-cols-[0.9fr,1.1fr]">
                <div className={`${panelClassName} p-6`}>
                  <div className="flex items-start justify-between gap-4">
                    <SectionHeading
                      eyebrow="Strongest Edge"
                      title="Highest-ranked relationship"
                      description="Use this as the first candidate pair when explaining why MBA is proposing bundle combinations."
                    />
                    <UserGroupIcon className="h-11 w-11 rounded-2xl bg-minteal-50 p-2.5 text-minteal-700" />
                  </div>

                  {strongestEdge ? (
                    <div className="mt-5 rounded-[1.7rem] border border-minteal-100 bg-minteal-50/70 p-5">
                      <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Relationship</p>
                      <p className="mt-3 text-2xl font-semibold text-minteal-950">
                        {strongestEdge.source} {'->'} {strongestEdge.target}
                      </p>
                      <div className="mt-5 grid gap-3 sm:grid-cols-2">
                        <div className="rounded-[1.2rem] border border-minteal-100 bg-white p-4">
                          <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Support</p>
                          <p className="mt-2 text-lg font-semibold text-minteal-950">{formatRatioPercent(strongestEdge.value)}</p>
                        </div>
                        <div className="rounded-[1.2rem] border border-minteal-100 bg-white p-4">
                          <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Confidence</p>
                          <p className="mt-2 text-lg font-semibold text-minteal-950">{formatRatioPercent(strongestEdge.avg_confidence)}</p>
                        </div>
                        <div className="rounded-[1.2rem] border border-minteal-100 bg-white p-4">
                          <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Lift</p>
                          <p className="mt-2 text-lg font-semibold text-minteal-950">{roundNumber(strongestEdge.avg_lift, 2)}</p>
                        </div>
                        <div className="rounded-[1.2rem] border border-minteal-100 bg-white p-4">
                          <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Strength score</p>
                          <p className="mt-2 text-lg font-semibold text-minteal-950">{roundNumber(strongestEdge.strength_score, 3)}</p>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-5">
                      <EmptyState message="No relationship edge available." />
                    </div>
                  )}
                </div>

                <div className={`${panelClassName} p-6`}>
                  <div className="flex items-start justify-between gap-4">
                    <SectionHeading
                      eyebrow="Edge Table"
                      title="Top MBA relationships"
                      description="A ranked list of the highest-strength relationships returned by the Sankey API."
                    />
                    <ChartBarIcon className="h-11 w-11 rounded-2xl bg-minteal-50 p-2.5 text-minteal-700" />
                  </div>

                  <div className="mt-5 overflow-hidden rounded-[1.6rem] border border-minteal-100">
                    <div className="max-h-[360px] overflow-auto">
                      <table className="min-w-full divide-y divide-minteal-100 text-left text-sm">
                        <thead className="sticky top-0 bg-minteal-50 text-minteal-500">
                          <tr>
                            <th className="px-4 py-3 font-semibold">Source</th>
                            <th className="px-4 py-3 font-semibold">Target</th>
                            <th className="px-4 py-3 font-semibold">Support</th>
                            <th className="px-4 py-3 font-semibold">Confidence</th>
                            <th className="px-4 py-3 font-semibold">Lift</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-minteal-100 bg-white text-minteal-900">
                          {mbaSankey.edge_table.map((edge) => (
                            <tr key={`${edge.source}-${edge.target}`}>
                              <td className="px-4 py-3 font-medium">{edge.source}</td>
                              <td className="px-4 py-3 font-medium">{edge.target}</td>
                              <td className="px-4 py-3">{formatRatioPercent(edge.value)}</td>
                              <td className="px-4 py-3">{formatRatioPercent(edge.avg_confidence)}</td>
                              <td className="px-4 py-3">{roundNumber(edge.avg_lift, 2)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </section>
            </>
          ) : null}
        </div>
      </section>
    </div>
  )
}

export default BundleGenerationPage


