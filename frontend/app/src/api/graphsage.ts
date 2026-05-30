import axios from 'axios'

export type FeatureOption = {
  values: string[]
  total_values: number
  truncated: boolean
}

export type NumericRange = {
  min: number
  max: number
}

export type GraphSageFeatureOptions = {
  user_features: {
    service_class_category: FeatureOption
    canal: FeatureOption
    payment_mode: FeatureOption
    department_city: FeatureOption
    brand_name: FeatureOption
    device_capability: FeatureOption
  }
  bundle_features: {
    bundle_type: FeatureOption
  }
  numeric_ranges: {
    price: NumericRange
    configured_volume_mb: NumericRange
    configured_volume_min: NumericRange
    configured_volume_sms: NumericRange
    validity_hours: NumericRange
    distinct_users: NumericRange
    total_subscriptions: NumericRange
    total_revenue: NumericRange
  }
  counts: {
    users: number
    bundles: number
    train_edges: number
  }
}

export type Recommendation = {
  rank: number
  msisdn: string
  user_idx: number | null
  bundle_idx: number
  bundle_id: string
  bundle_name: string
  bundle_type: string
  price: number
  score: number
  recommendation_type: string
  matched_features?: string[]
  cohort_size?: number | null
}

export type RecommendationResponse = {
  count: number
  recommendations: Recommendation[]
}

export type RecommendationsPageResponse = {
  total_returned: number
  offset: number
  limit: number
  recommendations: Recommendation[]
}

export type RecommendationsByMsisdnResponse = {
  msisdn: string
  total_returned: number
  recommendations: Recommendation[]
}

export type SingleRecommendationRequest = {
  msisdn: string
  top_k: number
  exclude_seen: boolean
}

export type BatchRecommendationRequest = {
  msisdns: string[]
  top_k: number
  exclude_seen: boolean
  include_cold_start: boolean
  user_chunk_size: number
  cold_start_profiles?: Record<string, ColdStartProfile>
}

export type ColdStartProfile = {
  service_class_category: string
  canal: string
  payment_mode: string
  department_city: string
  brand_name: string
  device_capability: string
  bundle_type: string
  min_price?: number
  max_price?: number
  min_cohort_users: number
}

export type ColdStartRecommendationRequest = ColdStartProfile & {
  msisdn: string
  top_k: number
}

export type ColdStartFeatureOptions = {
  service_class_category: string[]
  canal: string[]
  payment_mode: string[]
  department_city: string[]
  brand_name: string[]
  device_capability: string[]
  bundle_type: string[]
  min_price: number
  max_price: number
}

export type ColdStartRecommendationsResponse = {
  msisdn: string
  total_returned: number
  recommendations: Recommendation[]
}

export type GraphNode = {
  id: string
  node_type: 'user' | 'bundle' | string
  label: string
  raw_id: string
  index: number
  features: Record<string, unknown>
}

export type GraphLink = {
  source: string
  target: string
  edge_type: string
  weight: number
  features: Record<string, unknown>
}

export type GraphVisualizationResponse = {
  summary: {
    node_count: number
    link_count: number
    user_count: number
    bundle_count: number
    returned_edges: number
    available_edges_after_filters: number
  }
  filters: Record<string, unknown>
  nodes: GraphNode[]
  links: GraphLink[]
}

export type GraphVisualizationFilters = {
  max_edges: number
  bundle_type?: string
  msisdn?: string
  min_price?: number
  max_price?: number
}

export type GraphStatsResponse = {
  msisdn_nodes: number
  bundle_nodes: number
  total_edges: number
}

export type GraphSampleNode = {
  id: string
  node_type: string
  label: string
  features: Record<string, unknown>
}

export type GraphSampleEdge = {
  id: string
  source: string
  target: string
  edge_type: string
  features: Record<string, unknown>
}

export type GraphSampleResponse = {
  nodes: GraphSampleNode[]
  edges: GraphSampleEdge[]
  node_count: number
  edge_count: number
  truncated: boolean
}

export type GraphSearchResponse = {
  total_returned: number
  results: GraphSampleNode[]
}

export const graphsageApiBaseUrl =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) ??
    (import.meta.env.VITE_PRICING_API_BASE_URL as string | undefined) ??
    'http://127.0.0.1:8000').replace(/\/$/, '')

const graphSageClient = axios.create({
  baseURL: graphsageApiBaseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const getApiErrorMessage = (error: unknown) => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail

    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }

    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((item) => {
          if (typeof item === 'string') {
            return item
          }

          if (item && typeof item === 'object' && 'msg' in item) {
            return String(item.msg)
          }

          return String(item)
        })
        .join(', ')
    }

    return error.message
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Unexpected API error'
}

const appendNumberFilter = (params: URLSearchParams, key: string, value?: number) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    params.set(key, String(value))
  }
}

export const graphsageApi = {
  async getFeatureOptions() {
    const { data } = await graphSageClient.get<GraphSageFeatureOptions>('/graphsage/features/options')
    return data
  },

  async getGraphStats() {
    const { data } = await graphSageClient.get<GraphStatsResponse>('/graph/stats')
    return data
  },

  async getGraphSample(maxEdges = 500, maxUsers = 1000, maxBundles = 500) {
    const params = new URLSearchParams()
    appendNumberFilter(params, 'max_edges', maxEdges)
    appendNumberFilter(params, 'max_users', maxUsers)
    appendNumberFilter(params, 'max_bundles', maxBundles)

    const { data } = await graphSageClient.get<GraphSampleResponse>(`/graph/sample?${params.toString()}`)
    return data
  },

  async getMsisdnNeighborhood(msisdn: string, maxEdges = 1000) {
    const params = new URLSearchParams()
    appendNumberFilter(params, 'max_edges', maxEdges)

    const { data } = await graphSageClient.get<GraphSampleResponse>(
      `/graph/neighborhood/msisdn/${encodeURIComponent(msisdn)}?${params.toString()}`,
    )
    return data
  },

  async getBundleNeighborhood(bundleId: string, maxEdges = 100) {
    const params = new URLSearchParams()
    appendNumberFilter(params, 'max_edges', maxEdges)

    const { data } = await graphSageClient.get<GraphSampleResponse>(
      `/graph/neighborhood/bundle/${encodeURIComponent(bundleId)}?${params.toString()}`,
    )
    return data
  },

  async searchGraph(q: string, nodeType: 'all' | 'user' | 'bundle' = 'all', limit = 20) {
    const params = new URLSearchParams()
    params.set('q', q)
    params.set('node_type', nodeType)
    appendNumberFilter(params, 'limit', limit)

    const { data } = await graphSageClient.get<GraphSearchResponse>(`/graph/search?${params.toString()}`)
    return data
  },

  async recommend(payload: SingleRecommendationRequest) {
    const { data } = await graphSageClient.post<RecommendationResponse>('/graphsage/recommend', payload)
    return data
  },

  async recommendBatch(payload: BatchRecommendationRequest) {
    const { data } = await graphSageClient.post<unknown>('/graphsage/recommend/batch', payload)
    return data
  },

  async recommendColdStart(payload: ColdStartRecommendationRequest) {
    const { data } = await graphSageClient.post<RecommendationResponse>('/graphsage/recommend/cold-start', payload)
    return data
  },

  async getColdStartFeatures() {
    const { data } = await graphSageClient.get<ColdStartFeatureOptions>('/graphsage/cold-start/features')
    return data
  },

  async getColdStartRecommendations(payload: ColdStartRecommendationRequest) {
    const { data } = await graphSageClient.post<ColdStartRecommendationsResponse>(
      '/graphsage/cold-start/recommendations',
      payload,
    )
    return data
  },

  async getRecommendationsPage(offset: number, limit: number) {
    const params = new URLSearchParams()
    appendNumberFilter(params, 'offset', offset)
    appendNumberFilter(params, 'limit', limit)

    const { data } = await graphSageClient.get<RecommendationsPageResponse>(
      `/graphsage/recommendations?${params.toString()}`,
    )
    return data
  },

  async getRecommendationsByMsisdn(msisdn: string, topK: number) {
    const params = new URLSearchParams()
    appendNumberFilter(params, 'top_k', topK)

    const { data } = await graphSageClient.get<RecommendationsByMsisdnResponse>(
      `/graphsage/recommendations/${encodeURIComponent(msisdn)}?${params.toString()}`,
    )
    return data
  },

  async getGraphVisualization(filters: GraphVisualizationFilters) {
    const params = new URLSearchParams()
    appendNumberFilter(params, 'max_edges', filters.max_edges)
    appendNumberFilter(params, 'min_price', filters.min_price)
    appendNumberFilter(params, 'max_price', filters.max_price)

    if (filters.bundle_type?.trim()) {
      params.set('bundle_type', filters.bundle_type.trim())
    }

    if (filters.msisdn?.trim()) {
      params.set('msisdn', filters.msisdn.trim())
    }

    const { data } = await graphSageClient.get<GraphVisualizationResponse>(
      `/graphsage/graph/visualization?${params.toString()}`,
    )
    return data
  },
}
