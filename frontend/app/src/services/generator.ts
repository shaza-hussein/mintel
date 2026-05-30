import axios from 'axios'

export type OfferType = 'atl' | 'diy_mode' | 'promotion_mode' | 'btl_normal' | 'btl_moderate' | 'btl_aggressive'

export type GeneratorBundleType = 'BUNDLE_DATA' | 'BUNDLE_VOICE' | 'BUNDLE_SMS'

export type BundleGeneratorRequestPayload = {
  offer_type: OfferType
  allowed_bundle_types: GeneratorBundleType[]
  validity_options: number[]
  max_volume_mb: number
  max_volume_min: number
  max_volume_sms: number
  samples_per_type: number
  top_n: number
}

export type GeneratorExistingBundleItem = {
  bundle_id: number | string
  bundle_name: string
  price: number
  volume_mb: number
  bundle_type: string
  minutes: number
  sms: number
  avg_weekly_revenue: number
  avg_weekly_subs: number
  popularity_score: number
}

export type GeneratorGeneratedBundleItem = {
  bundle_id: number | string
  bundle_type: string
  usage_type?: string | null
  service_class_category?: string | null
  price: number
  volume_mb: number
  volume_min: number
  volume_sms: number
  validity_hours: number
  validity_days: number
  validity_bucket?: string | null
  predicted_popularity?: number | null
  popularity_category?: string | null
}

export type GeneratorMeta = {
  existing_count: number
  generated_count: number
  summary_count: number
  top_per_type_count: number
}

export type GeneratorModelParams = {
  growth_rate: number
  cannib_sensitivity: number
  price_elasticity: number
  similarity_threshold: number
  cannib_cap: number
  expected_new_market_pct: number
  cross_type_penalty: number
  feature_weights: Record<string, number>
}

export type BundleGeneratorApiResponse = {
  request: BundleGeneratorRequestPayload
  meta: GeneratorMeta
  model_params: GeneratorModelParams
  existing_bundles: GeneratorExistingBundleItem[]
  generated_bundles: GeneratorGeneratedBundleItem[]
  summary: Array<Record<string, unknown>>
  top_per_type: Array<Record<string, unknown>>
  impact_rows: Array<Record<string, unknown>>
}

const API_BASE_URL =
  (import.meta.env.VITE_PRICING_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ??
  'http://127.0.0.1:8000'

export const generateBundles = async (payload: BundleGeneratorRequestPayload) => {
  const response = await axios.post<BundleGeneratorApiResponse>(`${API_BASE_URL}/generator/bundles`, payload)
  return response.data
}
