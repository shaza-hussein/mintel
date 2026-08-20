import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from 'react'
import {
  ArrowDownTrayIcon,
  ArrowPathIcon,
  BoltIcon,
  CheckCircleIcon,
  CpuChipIcon,
  CubeTransparentIcon,
  MagnifyingGlassIcon,
  SignalIcon,
  SparklesIcon,
  TableCellsIcon,
  UserCircleIcon,
} from '@heroicons/react/24/outline'
import {
  getApiErrorMessage,
  graphsageApi,
  type ColdStartFeatureOptions,
  type ColdStartRecommendationRequest,
  type GraphSampleNode,
  type GraphSampleResponse,
  type GraphStatsResponse,
  type Recommendation as GraphSageRecommendation,
} from '../api/graphsage'

type DashboardTab = 'graph' | 'predictions' | 'cold-start' | 'export'
type EdgeType = 'subscribed' | 'communication'

type MsisdnNode = {
  id: string
  type: 'msisdn'
  msisdn: string
  city: string
  brand: string
  deviceType: string
  arpu: string
  tenure: string
  dataUsageGB: number
  voiceMinutes: number
  age: number
  churnRisk: number
  x: number
  y: number
  z: number
}

type BundleNode = {
  id: string
  type: 'bundle'
  name: string
  bundleType: string
  price: number
  data_gb: number
  minutes: number
  subscriberCount: number
  x: number
  y: number
  z: number
}

type GraphEdge = {
  source: string
  target: string
  type: EdgeType
  weight: number
  since?: string
  callCount?: number
}

type RealGraphNode = {
  id: string
  type: 'msisdn' | 'bundle'
  label: string
  features: Record<string, unknown>
  x: number
  y: number
  z: number
  msisdn?: string
  city?: string
  brand?: string
  deviceType?: string
  name?: string
  bundleId?: string
  bundleType?: string
  price?: number
  dataMb?: number
  minutes?: number
  sms?: number
  activeDays?: number
  rawEvents?: number
  subscriptions?: number
  revenue?: number
  distinctUsers?: number
}

type RealGraphEdge = {
  id: string
  source: string
  target: string
  type: string
  features: Record<string, unknown>
}

type RealGraphData = {
  nodes: RealGraphNode[]
  edges: RealGraphEdge[]
  nodeCount: number
  edgeCount: number
  truncated: boolean
}

type Recommendation = {
  bundle: BundleNode
  score: number
  confidence: number
  reason: string
}

type Projection = RealGraphNode & {
  screenX: number
  screenY: number
  depth: number
  visible: boolean
}

const cities = ['Cairo', 'Alexandria', 'Giza', 'Luxor', 'Aswan', 'Mansoura', 'Tanta', 'Suez', 'Port Said', 'Ismailia']
const brands = ['Samsung', 'Apple', 'Huawei', 'Xiaomi', 'Oppo', 'Realme', 'Nokia', 'Tecno']
const deviceTypes = ['Smartphone', 'Feature Phone', 'Tablet', 'MiFi']
const arpuSegments = ['Low', 'Medium', 'High', 'Premium']
const tenures = ['0-6m', '6-12m', '1-2y', '2-5y', '5y+']

const bundleSeed: Array<Omit<BundleNode, 'id' | 'type' | 'subscriberCount' | 'x' | 'y' | 'z'>> = [
  { name: 'Social Max 10', bundleType: 'Social', price: 65, data_gb: 10, minutes: 250 },
  { name: 'Stream Plus 25', bundleType: 'Data', price: 145, data_gb: 25, minutes: 400 },
  { name: 'Family Share 40', bundleType: 'Hybrid', price: 240, data_gb: 40, minutes: 1200 },
  { name: 'Premium Roam 60', bundleType: 'Premium', price: 420, data_gb: 60, minutes: 1800 },
  { name: 'Talk Easy 5', bundleType: 'Voice', price: 45, data_gb: 5, minutes: 700 },
  { name: 'Night Data 30', bundleType: 'Data', price: 115, data_gb: 30, minutes: 150 },
  { name: 'Youth Mix 18', bundleType: 'Hybrid', price: 95, data_gb: 18, minutes: 550 },
  { name: 'Business Pro 80', bundleType: 'Premium', price: 560, data_gb: 80, minutes: 2600 },
  { name: 'Starter Voice 3', bundleType: 'Voice', price: 30, data_gb: 3, minutes: 450 },
  { name: 'Home MiFi 100', bundleType: 'Data', price: 680, data_gb: 100, minutes: 100 },
  { name: 'Traveler Flex 20', bundleType: 'Roaming', price: 310, data_gb: 20, minutes: 900 },
  { name: 'Daily Boost 8', bundleType: 'Add-on', price: 55, data_gb: 8, minutes: 180 },
]

const navigation: Array<{ id: DashboardTab; label: string; icon: typeof CpuChipIcon }> = [
  { id: 'graph', label: 'Graph Explorer', icon: CpuChipIcon },
  { id: 'predictions', label: 'Predictions', icon: TableCellsIcon },
  { id: 'cold-start', label: 'Cold Start', icon: BoltIcon },
  { id: 'export', label: 'Export CSV', icon: ArrowDownTrayIcon },
]

const seededRandom = (seed: number) => {
  let value = seed
  return () => {
    value += 0x6d2b79f5
    let t = value
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

const wait = (milliseconds: number) =>
  new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds)
  })

const formatCompactNumber = (value: number) =>
  new Intl.NumberFormat('en', {
    notation: 'compact',
    maximumFractionDigits: value >= 10_000_000 ? 0 : 1,
  }).format(value)

const emptyRealGraph: RealGraphData = {
  nodes: [],
  edges: [],
  nodeCount: 0,
  edgeCount: 0,
  truncated: false,
}

const getStringFeature = (features: Record<string, unknown>, key: string, fallback = '') => {
  const value = features[key]
  return value == null ? fallback : String(value)
}

const getNumberFeature = (features: Record<string, unknown>, key: string, fallback = 0) => {
  const value = Number(features[key])
  return Number.isFinite(value) ? value : fallback
}

const normalizeGraphResponse = (response: GraphSampleResponse): RealGraphData => {
  const users = response.nodes.filter((node) => node.node_type === 'user')
  const bundles = response.nodes.filter((node) => node.node_type === 'bundle')

  const nodes = response.nodes.map<RealGraphNode>((node) => {
    const isBundle = node.node_type === 'bundle'
    const group = isBundle ? bundles : users
    const groupIndex = Math.max(group.findIndex((item) => item.id === node.id), 0)
    const angle = group.length > 0 ? (groupIndex / group.length) * Math.PI * 2 : 0
    const ring = groupIndex % 5
    const radius = isBundle ? 150 + (ring % 2) * 46 : 44 + ring * 27 + (groupIndex % 7) * 2
    const y = isBundle ? Math.sin(groupIndex * 0.91) * 70 : Math.cos(groupIndex * 0.73) * 92

    if (isBundle) {
      const name = getStringFeature(node.features, 'bundle_name', node.label)
      return {
        id: node.id,
        type: 'bundle',
        label: node.label,
        features: node.features,
        x: Math.cos(angle) * radius,
        y,
        z: Math.sin(angle) * radius,
        name,
        bundleId: getStringFeature(node.features, 'bundle_id', node.id.replace('bundle:', '')),
        bundleType: getStringFeature(node.features, 'bundle_type', 'Unknown'),
        price: getNumberFeature(node.features, 'price'),
        dataMb: getNumberFeature(node.features, 'configured_volume_mb'),
        minutes: getNumberFeature(node.features, 'configured_volume_min'),
        sms: getNumberFeature(node.features, 'configured_volume_sms'),
        rawEvents: getNumberFeature(node.features, 'raw_events'),
        subscriptions: getNumberFeature(node.features, 'total_subscriptions'),
        revenue: getNumberFeature(node.features, 'total_revenue'),
        distinctUsers: getNumberFeature(node.features, 'distinct_users'),
      }
    }

    return {
      id: node.id,
      type: 'msisdn',
      label: node.label,
      features: node.features,
      x: Math.cos(angle) * radius,
      y,
      z: Math.sin(angle) * radius,
      msisdn: getStringFeature(node.features, 'msisdn', node.label),
      city: getStringFeature(node.features, 'department_city', 'UnknownCity'),
      brand: getStringFeature(node.features, 'brand_name', 'Unknown'),
      deviceType: getStringFeature(node.features, 'device_capability', 'Unknown'),
      rawEvents: getNumberFeature(node.features, 'raw_events'),
      activeDays: getNumberFeature(node.features, 'active_days'),
      subscriptions: getNumberFeature(node.features, 'total_subscriptions'),
      revenue: getNumberFeature(node.features, 'total_revenue'),
      price: getNumberFeature(node.features, 'avg_price'),
    }
  })

  const validNodeIds = new Set(nodes.map((node) => node.id))

  return {
    nodes,
    edges: response.edges
      .filter((edge) => validNodeIds.has(edge.source) && validNodeIds.has(edge.target))
      .map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: edge.edge_type,
        features: edge.features,
      })),
    nodeCount: response.node_count,
    edgeCount: response.edge_count,
    truncated: response.truncated,
  }
}

const normalizeSingleGraphNode = (node: GraphSampleNode): RealGraphNode =>
  normalizeGraphResponse({ nodes: [node], edges: [], node_count: 1, edge_count: 0, truncated: false }).nodes[0]!

const createGraphData = () => {
  const random = seededRandom(42)
  const bundles: BundleNode[] = bundleSeed.map((bundle, index) => {
    const angle = (index / bundleSeed.length) * Math.PI * 2
    return {
      ...bundle,
      id: `bundle-${index + 1}`,
      type: 'bundle',
      subscriberCount: 350 + Math.round(random() * 4200),
      x: Math.cos(angle) * 175,
      y: Math.sin(index * 1.4) * 64,
      z: Math.sin(angle) * 175,
    }
  })

  const msisdns: MsisdnNode[] = Array.from({ length: 64 }, (_, index) => {
    const ring = index % 4
    const angle = index * 0.78
    const radius = 65 + ring * 45 + random() * 30
    const arpu = arpuSegments[Math.floor(random() * arpuSegments.length)]
    return {
      id: `msisdn-${index + 1}`,
      type: 'msisdn',
      msisdn: `2010${String(61000000 + index * 137).padStart(8, '0')}`,
      city: cities[Math.floor(random() * cities.length)],
      brand: brands[Math.floor(random() * brands.length)],
      deviceType: deviceTypes[Math.floor(random() * deviceTypes.length)],
      arpu,
      tenure: tenures[Math.floor(random() * tenures.length)],
      dataUsageGB: Math.round((2 + random() * (arpu === 'Premium' ? 90 : arpu === 'High' ? 55 : 28)) * 10) / 10,
      voiceMinutes: 80 + Math.round(random() * (arpu === 'Low' ? 700 : 2200)),
      age: 18 + Math.round(random() * 48),
      churnRisk: Math.round((0.08 + random() * 0.78) * 100) / 100,
      x: Math.cos(angle) * radius,
      y: (random() - 0.5) * 150,
      z: Math.sin(angle) * radius,
    }
  })

  const edges: GraphEdge[] = []
  msisdns.forEach((node, index) => {
    const subscriptionCount = 1 + Math.floor(random() * 3)
    for (let offset = 0; offset < subscriptionCount; offset += 1) {
      const target = bundles[(index + offset * 5 + Math.floor(random() * bundles.length)) % bundles.length]
      edges.push({
        source: node.id,
        target: target.id,
        type: 'subscribed',
        weight: 0.55 + random() * 0.45,
        since: `202${Math.floor(random() * 5)}-${String(1 + Math.floor(random() * 12)).padStart(2, '0')}-01`,
      })
    }
  })

  for (let index = 0; index < 132; index += 1) {
    const source = msisdns[Math.floor(random() * msisdns.length)]
    const target = msisdns[Math.floor(random() * msisdns.length)]
    if (source.id !== target.id) {
      edges.push({
        source: source.id,
        target: target.id,
        type: 'communication',
        weight: 0.1 + random() * 0.6,
        callCount: 1 + Math.round(random() * 74),
      })
    }
  }

  return {
    msisdns,
    bundles,
    nodes: [...msisdns, ...bundles],
    edges,
  }
}

const scoreBundle = (user: Pick<MsisdnNode, 'arpu' | 'dataUsageGB' | 'voiceMinutes' | 'brand' | 'deviceType' | 'tenure' | 'age'>, bundle: BundleNode) => {
  const priceCeiling = user.arpu === 'Premium' ? 700 : user.arpu === 'High' ? 420 : user.arpu === 'Medium' ? 210 : 95
  const priceFit = 1 - Math.min(1, Math.abs(bundle.price - priceCeiling * 0.62) / priceCeiling)
  const dataFit = 1 - Math.min(1, Math.abs(bundle.data_gb - user.dataUsageGB * 1.18) / 95)
  const voiceFit = 1 - Math.min(1, Math.abs(bundle.minutes - user.voiceMinutes * 1.08) / 2700)
  const premiumLift = user.brand === 'Apple' || user.deviceType === 'MiFi' ? 0.08 : 0
  const loyaltyLift = user.tenure === '5y+' || user.tenure === '2-5y' ? 0.06 : 0
  const youthLift = user.age < 28 && ['Social', 'Hybrid', 'Data'].includes(bundle.bundleType) ? 0.08 : 0
  return clamp(priceFit * 0.32 + dataFit * 0.28 + voiceFit * 0.24 + premiumLift + loyaltyLift + youthLift, 0.38, 0.96)
}

const recommendationReason = (user: Pick<MsisdnNode, 'city' | 'arpu' | 'dataUsageGB' | 'voiceMinutes' | 'brand'>, bundle: BundleNode) => {
  if (bundle.data_gb >= user.dataUsageGB * 1.1 && bundle.minutes >= user.voiceMinutes * 0.75) {
    return `Strong data and voice fit for ${user.city} ${user.arpu.toLowerCase()}-ARPU behavior.`
  }
  if (bundle.bundleType === 'Premium' || bundle.price > 300) {
    return `${user.brand} profile and spend segment indicate readiness for a richer package.`
  }
  if (bundle.bundleType === 'Voice') {
    return `Voice-heavy usage pattern benefits from higher minute allowance.`
  }
  return `Similar subscribers in ${user.city} convert well on this bundle mix.`
}

const predictForUser = (user: MsisdnNode, bundles: BundleNode[], limit = 5): Recommendation[] =>
  bundles
    .map((bundle, index) => {
      const score = scoreBundle(user, bundle) - index * 0.002
      return {
        bundle,
        score,
        confidence: clamp(0.52 + score * 0.42, 0.5, 0.92),
        reason: recommendationReason(user, bundle),
      }
    })
    .sort((left, right) => right.score - left.score)
    .slice(0, limit)

const StatCard = ({ icon: Icon, label, value, tone, delay }: { icon: typeof CpuChipIcon; label: string; value: string; tone: string; delay: number }) => (
  <div
    className="targeting-rise rounded-2xl border border-minteal-100 bg-white/90 p-4 shadow-sm backdrop-blur"
    style={{ animationDelay: `${delay}ms` }}
  >
    <div className="flex items-center justify-between gap-3">
      <div>
        <p className="text-xs uppercase tracking-[0.22em] text-minteal-400">{label}</p>
        <p className="mt-2 font-mono text-2xl font-bold text-minteal-950">{value}</p>
      </div>
      <div className={`rounded-lg p-2 ${tone}`}>
        <Icon className="h-5 w-5" />
      </div>
    </div>
  </div>
)

const MetricBar = ({ label, value, max, color }: { label: string; value: number; max: number; color: string }) => (
  <div>
    <div className="mb-2 flex items-center justify-between text-xs text-minteal-600">
      <span>{label}</span>
      <span className="font-mono text-minteal-950">{value.toLocaleString()}</span>
    </div>
    <div className="h-2 overflow-hidden rounded-full bg-minteal-100">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${clamp((value / max) * 100, 4, 100)}%` }} />
    </div>
  </div>
)

const Graph3D = ({
  graph,
  selectedId,
  onSelect,
  loading,
  error,
  onSearch,
  onLoadSample,
}: {
  graph: RealGraphData
  selectedId: string | null
  onSelect: (node: RealGraphNode) => void
  loading: boolean
  error: string | null
  onSearch: (query: string) => void
  onLoadSample: () => void
}) => {
  const frameRef = useRef<HTMLDivElement | null>(null)
  const dragRef = useRef<{ active: boolean; x: number; y: number }>({ active: false, x: 0, y: 0 })
  const animationRef = useRef<number | null>(null)
  const [dimensions, setDimensions] = useState({ width: 860, height: 560 })
  const [rotation, setRotation] = useState({ x: -0.22, y: 0.45 })
  const [zoom, setZoom] = useState(360)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  useEffect(() => {
    const element = frameRef.current
    if (!element) {
      return
    }

    const resizeObserver = new ResizeObserver(([entry]) => {
      setDimensions({
        width: entry.contentRect.width,
        height: entry.contentRect.height,
      })
    })
    resizeObserver.observe(element)
    return () => resizeObserver.disconnect()
  }, [])

  useEffect(() => {
    const animate = () => {
      if (!dragRef.current.active) {
        setRotation((current) => ({ ...current, y: current.y + 0.0014 }))
      }
      animationRef.current = window.requestAnimationFrame(animate)
    }

    animationRef.current = window.requestAnimationFrame(animate)
    return () => {
      if (animationRef.current !== null) {
        window.cancelAnimationFrame(animationRef.current)
      }
    }
  }, [])

  const projections = useMemo(() => {
    const sinY = Math.sin(rotation.y)
    const cosY = Math.cos(rotation.y)
    const sinX = Math.sin(rotation.x)
    const cosX = Math.cos(rotation.x)
    const scale = zoom / 260
    const perspective = 640

    return graph.nodes.reduce<Record<string, Projection>>((acc, node) => {
      const rotatedX = node.x * cosY - node.z * sinY
      const z1 = node.x * sinY + node.z * cosY
      const rotatedY = node.y * cosX - z1 * sinX
      const rotatedZ = node.y * sinX + z1 * cosX
      const depthScale = perspective / (perspective + rotatedZ)
      acc[node.id] = {
        ...node,
        screenX: dimensions.width / 2 + rotatedX * scale * depthScale,
        screenY: dimensions.height / 2 + rotatedY * scale * depthScale,
        depth: rotatedZ,
        visible: depthScale > 0.45,
      }
      return acc
    }, {})
  }, [dimensions.height, dimensions.width, graph.nodes, rotation.x, rotation.y, zoom])

  const sortedNodes = useMemo(
    () => Object.values(projections).sort((left, right) => left.depth - right.depth),
    [projections],
  )

  const matchingNodes = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) {
      return new Set<string>()
    }

    return new Set(
      graph.nodes
        .filter((node) =>
          `${node.label} ${node.msisdn ?? ''} ${node.city ?? ''} ${node.brand ?? ''} ${node.name ?? ''} ${
            node.bundleId ?? ''
          } ${node.bundleType ?? ''}`
            .toLowerCase()
            .includes(normalized),
        )
        .map((node) => node.id),
    )
  }, [graph.nodes, query])

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    dragRef.current = { active: true, x: event.clientX, y: event.clientY }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragRef.current.active) {
      return
    }

    const deltaX = event.clientX - dragRef.current.x
    const deltaY = event.clientY - dragRef.current.y
    dragRef.current = { active: true, x: event.clientX, y: event.clientY }
    setRotation((current) => ({
      x: clamp(current.x + deltaY * 0.006, -1.15, 1.15),
      y: current.y + deltaX * 0.006,
    }))
  }

  const handlePointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    dragRef.current.active = false
    event.currentTarget.releasePointerCapture(event.pointerId)
  }

  const handleWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    event.preventDefault()
    setZoom((current) => clamp(current - event.deltaY * 0.45, 100, 600))
  }

  const findFirstMatch = () => {
    const first = graph.nodes.find((node) => matchingNodes.has(node.id))
    if (first) {
      onSelect(first)
      return
    }

    if (query.trim()) {
      onSearch(query.trim())
    }
  }

  return (
    <div className="min-h-[620px] overflow-hidden rounded-2xl border border-minteal-100 bg-white/90 shadow-sm">
      <div className="flex flex-col gap-3 border-b border-minteal-100 bg-minteal-50/80 p-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2 rounded-xl border border-minteal-200 bg-white px-3 py-2">
          <MagnifyingGlassIcon className="h-4 w-4 text-minteal-500" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                findFirstMatch()
              }
            }}
            placeholder="Search MSISDN, city, bundle"
            className="w-full bg-transparent text-sm text-minteal-900 outline-none placeholder:text-minteal-300 md:w-72"
          />
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={findFirstMatch}
            disabled={loading}
            className="rounded-xl border border-minteal-200 bg-white px-3 py-2 text-xs font-semibold text-minteal-700 transition hover:border-minteal-300 hover:bg-minteal-50 disabled:cursor-wait disabled:text-minteal-300"
          >
            Find
          </button>
          <button
            type="button"
            onClick={onLoadSample}
            disabled={loading}
            className="rounded-xl border border-minteal-200 bg-white px-3 py-2 text-xs font-semibold text-minteal-700 transition hover:border-minteal-300 hover:bg-minteal-50 disabled:cursor-wait disabled:text-minteal-300"
          >
            Sample
          </button>
          <button
            type="button"
            onClick={() => {
              setRotation({ x: -0.22, y: 0.45 })
              setZoom(360)
            }}
            className="inline-flex items-center gap-2 rounded-xl bg-minteal-900 px-3 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-minteal-800"
          >
            <ArrowPathIcon className="h-4 w-4" />
            Reset view
          </button>
        </div>
      </div>

      {error ? (
        <div className="border-b border-red-100 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {error}
        </div>
      ) : null}

      <div
        ref={frameRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onWheel={handleWheel}
        className="relative h-[560px] touch-none select-none overflow-hidden"
        style={{
          background:
            'radial-gradient(circle at 18% 22%, rgba(76,124,124,0.14), transparent 28%), radial-gradient(circle at 82% 28%, rgba(111,159,156,0.16), transparent 26%), #f8fbfb',
        }}
      >
        {loading ? (
          <div className="absolute left-4 top-4 z-20 rounded-xl border border-minteal-100 bg-white/95 px-4 py-3 text-sm font-semibold text-minteal-700 shadow-sm">
            <span className="mr-2 inline-block h-2 w-2 animate-ping rounded-full bg-minteal-500" />
            Loading graph data...
          </div>
        ) : null}
        <div className="absolute bottom-4 left-4 z-20 rounded-xl border border-minteal-100 bg-white/90 px-3 py-2 text-xs font-semibold text-minteal-600 shadow-sm">
          {graph.nodeCount.toLocaleString()} nodes - {graph.edgeCount.toLocaleString()} edges{graph.truncated ? ' - truncated' : ''}
        </div>
        <div className="pointer-events-none absolute inset-0 opacity-70">
          {Array.from({ length: 42 }, (_, index) => (
            <span
              key={index}
              className="targeting-particle absolute h-1 w-1 rounded-full bg-minteal-400/60"
              style={{
                left: `${(index * 37) % 100}%`,
                top: `${(index * 19) % 100}%`,
                animationDelay: `${index * 130}ms`,
              }}
            />
          ))}
        </div>
        <div className="pointer-events-none absolute left-1/2 top-[68%] h-52 w-[86%] -translate-x-1/2 rotate-0 rounded-[50%] border border-minteal-200 bg-[linear-gradient(rgba(76,124,124,0.16)_1px,transparent_1px),linear-gradient(90deg,rgba(76,124,124,0.16)_1px,transparent_1px)] bg-[size:34px_34px] opacity-70 blur-[0.1px]" />

        <svg className="pointer-events-none absolute inset-0 h-full w-full">
          {graph.edges.map((edge, index) => {
            const source = projections[edge.source]
            const target = projections[edge.target]
            if (!source || !target || !source.visible || !target.visible) {
              return null
            }
            return (
              <line
                key={`${edge.source}-${edge.target}-${index}`}
                x1={source.screenX}
                y1={source.screenY}
                x2={target.screenX}
                y2={target.screenY}
                stroke={edge.type === 'subscribed_to' ? '#4c7c7c' : '#93bdb7'}
                strokeOpacity={edge.type === 'subscribed_to' ? 0.32 : 0.14}
                strokeWidth={edge.type === 'subscribed_to' ? 1.4 : 0.9}
              />
            )
          })}
        </svg>

        {sortedNodes.map((node) => {
          if (!node.visible) {
            return null
          }
          const isSelected = selectedId === node.id
          const isMatch = matchingNodes.has(node.id)
          const size = node.type === 'bundle' ? 24 : 18
          const label = node.type === 'msisdn' ? node.msisdn ?? node.label : node.name ?? node.label

          return (
            <button
              key={node.id}
              type="button"
              onPointerDown={(event) => {
                event.stopPropagation()
              }}
              onPointerMove={(event) => {
                event.stopPropagation()
              }}
              onPointerUp={(event) => {
                event.stopPropagation()
              }}
              onClick={(event) => {
                event.stopPropagation()
                onSelect(node)
              }}
              onPointerEnter={() => setHoveredId(node.id)}
              onPointerLeave={() => setHoveredId(null)}
              className="absolute z-10 flex items-center justify-center outline-none transition-transform duration-300"
              style={
                {
                  left: node.screenX,
                  top: node.screenY,
                  width: size,
                  height: size,
                  transform: `translate(-50%, -50%) scale(${isSelected ? 1.55 : isMatch ? 1.35 : 1})`,
                } as CSSProperties
              }
              aria-label={label}
            >
              {node.type === 'bundle' ? (
                <span
                  className={`h-full w-full rotate-45 rounded-[5px] border border-minteal-200 bg-minteal-700 shadow-[0_0_18px_rgba(76,124,124,0.45)] ${
                    isSelected || isMatch ? 'ring-2 ring-minteal-300' : ''
                  }`}
                />
              ) : (
                <span
                  className={`h-full w-full rounded-full border border-white bg-minteal-400 shadow-[0_0_18px_rgba(111,159,156,0.6)] ${
                    isSelected || isMatch ? 'ring-2 ring-minteal-900' : ''
                  }`}
                />
              )}
              {hoveredId === node.id ? (
                <span className="pointer-events-none absolute bottom-full left-1/2 mb-3 min-w-44 -translate-x-1/2 rounded-xl border border-minteal-100 bg-white/95 px-3 py-2 text-left text-xs text-minteal-800 shadow-lg">
                  <strong className="block text-minteal-950">{label}</strong>
                  <span className="text-minteal-500">
                    {node.type === 'msisdn'
                      ? `${node.city ?? 'UnknownCity'} - ${node.brand ?? 'Unknown'}`
                      : `${node.bundleType ?? 'Unknown'} - ${(node.price ?? 0).toLocaleString()} F`}
                  </span>
                </span>
              ) : null}
            </button>
          )
        })}
      </div>
    </div>
  )
}

const NodeDetailPanel = ({
  node,
  recommendations,
  loading,
  onPredict,
}: {
  node: RealGraphNode | null
  recommendations: GraphSageRecommendation[]
  loading: boolean
  onPredict: () => void
}) => {
  if (!node) {
    return (
      <aside className="rounded-2xl border border-minteal-100 bg-white/90 p-5 text-minteal-700 shadow-sm">
        <div className="flex h-full min-h-[430px] flex-col items-center justify-center text-center">
          <UserCircleIcon className="h-12 w-12 text-minteal-300" />
          <h3 className="mt-4 text-lg font-semibold text-minteal-950">Select a graph node</h3>
          <p className="mt-2 text-sm leading-6 text-minteal-500">Click an MSISDN sphere for subscriber details or a bundle octahedron for package metrics.</p>
        </div>
      </aside>
    )
  }

  if (node.type === 'bundle') {
    return (
      <aside className="rounded-2xl border border-minteal-100 bg-white/90 p-5 shadow-sm">
        <p className="text-xs uppercase tracking-[0.25em] text-minteal-400">Bundle node</p>
        <h3 className="mt-2 text-2xl font-bold text-minteal-950">{node.name ?? node.label}</h3>
        <div className="mt-5 grid gap-3 text-sm">
          {[
            ['Bundle ID', node.bundleId ?? 'N/A'],
            ['Type', node.bundleType ?? 'Unknown'],
            ['Price', `${(node.price ?? 0).toLocaleString()} F`],
            ['Data MB', (node.dataMb ?? 0).toLocaleString()],
            ['Minutes', (node.minutes ?? 0).toLocaleString()],
            ['SMS', (node.sms ?? 0).toLocaleString()],
            ['Distinct Users', node.distinctUsers == null ? 'N/A' : formatCompactNumber(node.distinctUsers)],
            ['Subscriptions', node.subscriptions == null ? 'N/A' : formatCompactNumber(node.subscriptions)],
            ['Revenue', node.revenue == null ? 'N/A' : formatCompactNumber(node.revenue)],
          ].map(([label, value]) => (
            <div key={label} className="flex items-center justify-between rounded-xl border border-minteal-100 bg-minteal-50 px-3 py-2">
              <span className="text-minteal-500">{label}</span>
              <span className="font-semibold text-minteal-950">{value}</span>
            </div>
          ))}
        </div>
        <div className="mt-5 rounded-xl border border-minteal-100 bg-minteal-50 p-4 text-sm leading-6 text-minteal-700">
          Bundle neighborhood is loaded from subscription edges. Select another node or search to inspect related subscribers and packages.
        </div>
      </aside>
    )
  }

  return (
    <aside className="rounded-2xl border border-minteal-100 bg-white/90 p-5 shadow-sm">
      <p className="text-xs uppercase tracking-[0.25em] text-minteal-400">MSISDN node</p>
      <h3 className="mt-2 font-mono text-xl font-bold text-minteal-950">{node.msisdn ?? node.label}</h3>
      <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
        {[
          ['City', node.city ?? 'UnknownCity'],
          ['Brand', node.brand ?? 'Unknown'],
          ['Device', node.deviceType ?? 'Unknown'],
          ['Service', getStringFeature(node.features, 'service_class_category', 'Unknown')],
          ['Canal', getStringFeature(node.features, 'canal', 'Unknown')],
          ['Payment', getStringFeature(node.features, 'payment_mode', 'Unknown')],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-minteal-100 bg-minteal-50 p-3">
            <p className="text-xs text-minteal-400">{label}</p>
            <p className="mt-1 truncate font-semibold text-minteal-950">{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-5 space-y-4">
        <MetricBar label="Raw Events" value={node.rawEvents ?? 0} max={300} color="bg-minteal-500" />
        <MetricBar label="Active Days" value={node.activeDays ?? 0} max={90} color="bg-minteal-800" />
      </div>
      <div className="mt-5 grid gap-3 text-sm">
        {[
          ['Subscriptions', node.subscriptions == null ? 'N/A' : formatCompactNumber(node.subscriptions)],
          ['Revenue', node.revenue == null ? 'N/A' : formatCompactNumber(node.revenue)],
          ['Average Price', node.price == null ? 'N/A' : `${Math.round(node.price).toLocaleString()} F`],
        ].map(([label, value]) => (
          <div key={label} className="flex items-center justify-between rounded-xl border border-minteal-100 bg-minteal-50 px-3 py-2">
            <span className="text-minteal-500">{label}</span>
            <span className="font-semibold text-minteal-950">{value}</span>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={onPredict}
        disabled={loading}
        className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-minteal-900 px-4 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-minteal-800 disabled:cursor-wait disabled:bg-minteal-500"
      >
        <SparklesIcon className="h-5 w-5" />
        {loading ? 'Loading saved recommendations...' : 'Load Saved Recommendations'}
      </button>
      <div className="mt-5 space-y-3">
        {loading ? (
          <div className="rounded-xl border border-minteal-100 bg-minteal-50 p-4 text-sm text-minteal-700">
            <span className="mr-2 inline-block h-2 w-2 animate-ping rounded-full bg-minteal-500" />
            Reading precomputed inference results for this MSISDN.
          </div>
        ) : null}
        {recommendations.map((recommendation, index) => (
          <div
            key={`${recommendation.bundle_id}-${recommendation.rank}`}
            className="targeting-rise rounded-xl border border-minteal-100 bg-minteal-50 p-3"
            style={{ animationDelay: `${index * 90}ms` }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-minteal-950">{recommendation.bundle_name || recommendation.bundle_id}</p>
                <p className="mt-1 text-xs text-minteal-500">
                  {recommendation.bundle_type || 'Unknown'} - {recommendation.price.toLocaleString()} F
                </p>
              </div>
              <span className="font-mono text-sm font-bold text-emerald-600">{formatGraphSageScore(recommendation.score)}</span>
            </div>
            <p className="mt-2 text-xs leading-5 text-minteal-600">
              {recommendation.matched_features && recommendation.matched_features.length > 0
                ? recommendation.matched_features.join(', ')
                : recommendation.recommendation_type || 'graphsage'}
            </p>
          </div>
        ))}
      </div>
    </aside>
  )
}

const formatGraphSageScore = (value: number) => (Number.isFinite(value) ? value.toFixed(4) : 'N/A')

const PredictionsPanel = () => {
  const [query, setQuery] = useState('')
  const [activeMsisdn, setActiveMsisdn] = useState('')
  const [recommendations, setRecommendations] = useState<GraphSageRecommendation[]>([])
  const [offset, setOffset] = useState(0)
  const [limit, setLimit] = useState(10)
  const [totalReturned, setTotalReturned] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isSearchMode = activeMsisdn.trim().length > 0
  const currentPage = Math.floor(offset / limit) + 1
  const canGoNext = !isSearchMode && recommendations.length === limit

  const loadRecommendations = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const response = isSearchMode
        ? await graphsageApi.getRecommendationsByMsisdn(activeMsisdn, Math.min(limit, 100))
        : await graphsageApi.getRecommendationsPage(offset, limit)

      setRecommendations(response.recommendations)
      setTotalReturned(response.total_returned)
    } catch (apiError) {
      setRecommendations([])
      setTotalReturned(0)
      setError(getApiErrorMessage(apiError))
    } finally {
      setLoading(false)
    }
  }, [activeMsisdn, isSearchMode, limit, offset])

  useEffect(() => {
    void loadRecommendations()
  }, [loadRecommendations])

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const nextMsisdn = query.trim()
    setOffset(0)
    setActiveMsisdn(nextMsisdn)
  }

  const handleClearSearch = () => {
    setQuery('')
    setActiveMsisdn('')
    setOffset(0)
  }

  const handleLimitChange = (event: FormEvent<HTMLSelectElement>) => {
    setLimit(Number(event.currentTarget.value))
    setOffset(0)
  }

  return (
    <section className="rounded-2xl border border-minteal-100 bg-white/90 p-5 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-minteal-400">Predictions overview</p>
          <h3 className="mt-2 text-2xl font-bold text-minteal-950">
            {isSearchMode ? `Recommendations for ${activeMsisdn}` : 'GraphSAGE recommendations'}
          </h3>
        </div>
        <form onSubmit={handleSearch} className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2 rounded-xl border border-minteal-200 bg-white px-3 py-2">
            <MagnifyingGlassIcon className="h-4 w-4 text-minteal-500" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search MSISDN"
              className="bg-transparent text-sm text-minteal-900 outline-none placeholder:text-minteal-300"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="rounded-xl bg-minteal-900 px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-minteal-800 disabled:cursor-wait disabled:bg-minteal-500"
          >
            Search
          </button>
          {isSearchMode ? (
            <button
              type="button"
              onClick={handleClearSearch}
              className="rounded-xl border border-minteal-200 bg-white px-4 py-2 text-sm font-semibold text-minteal-700 transition hover:border-minteal-300 hover:bg-minteal-50"
            >
              Show all
            </button>
          ) : null}
        </form>
      </div>

      <div className="mt-5 flex flex-col gap-3 rounded-xl border border-minteal-100 bg-minteal-50 px-3 py-3 text-sm text-minteal-600 md:flex-row md:items-center md:justify-between">
        <div>
          <span className="font-mono font-bold text-minteal-950">{totalReturned.toLocaleString()}</span>
          <span> recommendations returned</span>
          {!isSearchMode ? <span> on page {currentPage}</span> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-minteal-500">
            Limit
            <select
              value={limit}
              onChange={handleLimitChange}
              className="rounded-lg border border-minteal-200 bg-white px-2 py-1 text-sm font-semibold normal-case tracking-normal text-minteal-900 outline-none"
            >
              {[10, 25, 50, 100].map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => void loadRecommendations()}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl border border-minteal-200 bg-white px-3 py-2 text-xs font-semibold text-minteal-700 transition hover:border-minteal-300 hover:bg-minteal-50 disabled:cursor-wait disabled:text-minteal-300"
          >
            <ArrowPathIcon className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {error ? (
        <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {error}
        </div>
      ) : null}

      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[920px] border-separate border-spacing-y-2 text-left text-sm">
          <thead className="text-xs uppercase tracking-[0.16em] text-minteal-400">
            <tr>
              <th className="px-3 py-2">Rank</th>
              <th className="px-3 py-2">MSISDN</th>
              <th className="px-3 py-2">Bundle</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Price</th>
              <th className="px-3 py-2">Score</th>
              <th className="px-3 py-2">Source</th>
            </tr>
          </thead>
          <tbody>
            {recommendations.map((recommendation, index) => (
              <tr
                key={`${recommendation.msisdn}-${recommendation.bundle_id}-${recommendation.rank}-${index}`}
                className="targeting-rise bg-minteal-50 text-minteal-700 transition hover:bg-minteal-100"
                style={{ animationDelay: `${index * 45}ms` }}
              >
                <td className="rounded-l-xl px-3 py-3 font-mono font-bold text-minteal-950">{recommendation.rank}</td>
                <td className="px-3 py-3 font-mono text-minteal-950">{recommendation.msisdn}</td>
                <td className="px-3 py-3">
                  <p className="font-semibold text-minteal-950">{recommendation.bundle_name || recommendation.bundle_id}</p>
                  <p className="mt-1 font-mono text-xs text-minteal-500">{recommendation.bundle_id}</p>
                </td>
                <td className="px-3 py-3">{recommendation.bundle_type || 'Unknown'}</td>
                <td className="px-3 py-3 font-mono">{recommendation.price.toLocaleString()} F</td>
                <td className="px-3 py-3 font-mono font-bold text-emerald-600">{formatGraphSageScore(recommendation.score)}</td>
                <td className="rounded-r-xl px-3 py-3">{recommendation.recommendation_type || 'graphsage'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!loading && recommendations.length === 0 && !error ? (
        <div className="mt-5 rounded-xl border border-minteal-100 bg-minteal-50 px-4 py-5 text-sm text-minteal-600">
          No recommendations returned.
        </div>
      ) : null}

      {!isSearchMode ? (
        <div className="mt-5 flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={() => setOffset((current) => Math.max(0, current - limit))}
            disabled={loading || offset === 0}
            className="rounded-xl border border-minteal-200 bg-white px-4 py-2 text-sm font-semibold text-minteal-700 transition hover:border-minteal-300 hover:bg-minteal-50 disabled:cursor-not-allowed disabled:text-minteal-300"
          >
            Previous
          </button>
          <span className="font-mono text-sm text-minteal-600">offset {offset.toLocaleString()}</span>
          <button
            type="button"
            onClick={() => setOffset((current) => current + limit)}
            disabled={loading || !canGoNext}
            className="rounded-xl border border-minteal-200 bg-white px-4 py-2 text-sm font-semibold text-minteal-700 transition hover:border-minteal-300 hover:bg-minteal-50 disabled:cursor-not-allowed disabled:text-minteal-300"
          >
            Next
          </button>
        </div>
      ) : null}
    </section>
  )
}

type ColdStartForm = {
  msisdn: string
  top_k: string
  service_class_category: string
  canal: string
  payment_mode: string
  department_city: string
  brand_name: string
  device_capability: string
  bundle_type: string
  min_price: string
  max_price: string
  min_cohort_users: string
}

type ColdStartSelectKey =
  | 'service_class_category'
  | 'canal'
  | 'payment_mode'
  | 'department_city'
  | 'brand_name'
  | 'device_capability'
  | 'bundle_type'

const coldStartSelectFields: Array<{ key: ColdStartSelectKey; label: string }> = [
  { key: 'service_class_category', label: 'Service Class' },
  { key: 'canal', label: 'Canal' },
  { key: 'payment_mode', label: 'Payment Mode' },
  { key: 'department_city', label: 'Department / City' },
  { key: 'brand_name', label: 'Brand Name' },
  { key: 'device_capability', label: 'Device Capability' },
  { key: 'bundle_type', label: 'Bundle Type' },
]

const initialColdStartForm: ColdStartForm = {
  msisdn: 'cold_start_user',
  top_k: '10',
  service_class_category: '',
  canal: '',
  payment_mode: '',
  department_city: '',
  brand_name: '',
  device_capability: '',
  bundle_type: '',
  min_price: '100',
  max_price: '150',
  min_cohort_users: '100',
}

const getFirstOption = (options: string[]) => options[0] ?? ''

const applyColdStartFeatureDefaults = (form: ColdStartForm, features: ColdStartFeatureOptions): ColdStartForm => {
  const nextForm = { ...form }

  coldStartSelectFields.forEach(({ key }) => {
    const options = features[key]
    if (!options.includes(nextForm[key])) {
      nextForm[key] = getFirstOption(options)
    }
  })

  if (features.min_price <= 100 && features.max_price >= 150) {
    nextForm.min_price = '100'
    nextForm.max_price = '150'
  } else {
    nextForm.min_price = String(features.min_price)
    nextForm.max_price = String(features.max_price)
  }

  return nextForm
}

const ColdStartPanel = () => {
  const [features, setFeatures] = useState<ColdStartFeatureOptions | null>(null)
  const [form, setForm] = useState<ColdStartForm>(initialColdStartForm)
  const [featuresLoading, setFeaturesLoading] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [totalReturned, setTotalReturned] = useState(0)
  const [results, setResults] = useState<GraphSageRecommendation[]>([])

  useEffect(() => {
    let ignore = false

    const loadFeatures = async () => {
      setFeaturesLoading(true)
      setError(null)

      try {
        const featureOptions = await graphsageApi.getColdStartFeatures()
        if (!ignore) {
          setFeatures(featureOptions)
          setForm((current) => applyColdStartFeatureDefaults(current, featureOptions))
        }
      } catch (apiError) {
        if (!ignore) {
          setError(getApiErrorMessage(apiError))
        }
      } finally {
        if (!ignore) {
          setFeaturesLoading(false)
        }
      }
    }

    void loadFeatures()

    return () => {
      ignore = true
    }
  }, [])

  const updateForm = <Key extends keyof ColdStartForm>(key: Key, value: ColdStartForm[Key]) => {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const topK = clamp(Math.round(Number(form.top_k) || 10), 1, 100)
    const minPrice = Number(form.min_price)
    const maxPrice = Number(form.max_price)
    const minCohortUsers = Math.max(1, Math.round(Number(form.min_cohort_users) || 100))

    if (!Number.isFinite(minPrice) || !Number.isFinite(maxPrice) || minPrice > maxPrice) {
      setError('Enter a valid price range.')
      return
    }

    const payload: ColdStartRecommendationRequest = {
      msisdn: form.msisdn.trim() || 'cold_start_user',
      top_k: topK,
      service_class_category: form.service_class_category,
      canal: form.canal,
      payment_mode: form.payment_mode,
      department_city: form.department_city,
      brand_name: form.brand_name,
      device_capability: form.device_capability,
      bundle_type: form.bundle_type,
      min_price: minPrice,
      max_price: maxPrice,
      min_cohort_users: minCohortUsers,
    }

    setLoading(true)
    setSubmitted(true)
    setError(null)
    setResults([])
    setTotalReturned(0)

    try {
      const response = await graphsageApi.getColdStartRecommendations(payload)
      setResults(response.recommendations)
      setTotalReturned(response.total_returned)
    } catch (apiError) {
      setError(getApiErrorMessage(apiError))
    } finally {
      setLoading(false)
    }
  }

  const selectClass = 'mt-2 w-full rounded-xl border border-minteal-200 bg-white px-3 py-2 text-sm text-minteal-900 outline-none transition focus:border-minteal-500 focus:ring-2 focus:ring-minteal-100 disabled:cursor-wait disabled:bg-minteal-50 disabled:text-minteal-300'
  const inputClass = 'mt-2 w-full rounded-xl border border-minteal-200 bg-white px-3 py-2 text-sm text-minteal-900 outline-none transition focus:border-minteal-500 focus:ring-2 focus:ring-minteal-100'

  return (
    <section className="space-y-5">
      <form onSubmit={handleSubmit} className="rounded-2xl border border-minteal-100 bg-white/90 p-5 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-minteal-400">Cold-start recommendation</p>
            <h3 className="mt-2 text-2xl font-bold text-minteal-950">New subscriber profile</h3>
          </div>
          <div className="rounded-xl border border-minteal-100 bg-minteal-50 px-3 py-2 text-xs font-semibold text-minteal-600">
            {featuresLoading ? 'Loading feature options...' : `${totalReturned.toLocaleString()} recommendations returned`}
          </div>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <label className="text-sm font-medium text-minteal-700">
            MSISDN
            <input
              value={form.msisdn}
              onChange={(event) => updateForm('msisdn', event.target.value)}
              className={inputClass}
            />
          </label>

          <label className="text-sm font-medium text-minteal-700">
            Top K
            <input
              type="number"
              min={1}
              max={100}
              value={form.top_k}
              onChange={(event) => updateForm('top_k', event.target.value)}
              className={inputClass}
            />
          </label>

          {coldStartSelectFields.map(({ key, label }) => (
            <label key={key} className="text-sm font-medium text-minteal-700">
              {label}
              <select
                value={form[key]}
                onChange={(event) => updateForm(key, event.target.value)}
                disabled={featuresLoading || !features}
                className={selectClass}
              >
                {(features?.[key] ?? []).map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          ))}

          <label className="text-sm font-medium text-minteal-700">
            Min Price
            <input
              type="number"
              min={features?.min_price}
              max={features?.max_price}
              value={form.min_price}
              onChange={(event) => updateForm('min_price', event.target.value)}
              className={inputClass}
            />
          </label>

          <label className="text-sm font-medium text-minteal-700">
            Max Price
            <input
              type="number"
              min={features?.min_price}
              max={features?.max_price}
              value={form.max_price}
              onChange={(event) => updateForm('max_price', event.target.value)}
              className={inputClass}
            />
          </label>

          <label className="text-sm font-medium text-minteal-700">
            Min Cohort Users
            <input
              type="number"
              min={1}
              value={form.min_cohort_users}
              onChange={(event) => updateForm('min_cohort_users', event.target.value)}
              className={inputClass}
            />
          </label>
        </div>

        <button
          type="submit"
          disabled={loading || featuresLoading || !features}
          className="mt-5 inline-flex items-center justify-center gap-2 rounded-xl bg-minteal-900 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-minteal-800 disabled:cursor-wait disabled:bg-minteal-500"
        >
          <BoltIcon className="h-5 w-5" />
          {loading ? 'Scoring profile...' : 'Generate recommendations'}
        </button>
      </form>

      {error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm font-semibold text-red-700">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-2xl border border-minteal-100 bg-minteal-50 p-5 text-minteal-700">
          <span className="mr-2 inline-block h-2 w-2 animate-ping rounded-full bg-minteal-500" />
          Building cohort recommendations from selected subscriber features.
        </div>
      ) : null}

      {results.length > 0 ? (
        <div className="overflow-x-auto rounded-2xl border border-minteal-100 bg-white/90 p-5 shadow-sm">
          <table className="w-full min-w-[980px] border-separate border-spacing-y-2 text-left text-sm">
            <thead className="text-xs uppercase tracking-[0.16em] text-minteal-400">
              <tr>
                <th className="px-3 py-2">Rank</th>
                <th className="px-3 py-2">Bundle</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Price</th>
                <th className="px-3 py-2">Score</th>
                <th className="px-3 py-2">Matched Features</th>
                <th className="px-3 py-2">Cohort</th>
              </tr>
            </thead>
            <tbody>
              {results.map((recommendation, index) => (
                <tr
                  key={`${recommendation.msisdn}-${recommendation.bundle_id}-${recommendation.rank}-${index}`}
                  className="targeting-rise bg-minteal-50 text-minteal-700 transition hover:bg-minteal-100"
                  style={{ animationDelay: `${index * 45}ms` }}
                >
                  <td className="rounded-l-xl px-3 py-3 font-mono font-bold text-minteal-950">{recommendation.rank}</td>
                  <td className="px-3 py-3">
                    <p className="font-semibold text-minteal-950">{recommendation.bundle_name || recommendation.bundle_id}</p>
                    <p className="mt-1 font-mono text-xs text-minteal-500">{recommendation.bundle_id}</p>
                  </td>
                  <td className="px-3 py-3">{recommendation.bundle_type || 'Unknown'}</td>
                  <td className="px-3 py-3 font-mono">{recommendation.price.toLocaleString()} F</td>
                  <td className="px-3 py-3 font-mono font-bold text-emerald-600">{formatGraphSageScore(recommendation.score)}</td>
                  <td className="px-3 py-3">
                    {recommendation.matched_features && recommendation.matched_features.length > 0
                      ? recommendation.matched_features.join(', ')
                      : 'N/A'}
                  </td>
                  <td className="rounded-r-xl px-3 py-3 font-mono">
                    {recommendation.cohort_size == null ? 'N/A' : formatCompactNumber(recommendation.cohort_size)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {submitted && !loading && results.length === 0 && !error ? (
        <div className="rounded-2xl border border-minteal-100 bg-minteal-50 p-5 text-sm text-minteal-600">
          No cold-start recommendations returned.
        </div>
      ) : null}
    </section>
  )
}

const ExportPanel = ({ msisdns, bundles }: { msisdns: MsisdnNode[]; bundles: BundleNode[] }) => {
  const [progress, setProgress] = useState(0)
  const [exporting, setExporting] = useState(false)
  const [success, setSuccess] = useState(false)

  const generateCsv = useCallback(async () => {
    setExporting(true)
    setSuccess(false)
    setProgress(0)

    const rows = [
      ['MSISDN', 'City', 'Brand', 'Device', 'ARPU', 'Tenure', 'Bundle_1', 'Score_1', 'Bundle_2', 'Score_2', 'Bundle_3', 'Score_3'],
    ]

    for (let index = 0; index < msisdns.length; index += 1) {
      const node = msisdns[index]
      const recommendations = predictForUser(node, bundles, 3)
      rows.push([
        node.msisdn,
        node.city,
        node.brand,
        node.deviceType,
        node.arpu,
        node.tenure,
        recommendations[0].bundle.name,
        String(Math.round(recommendations[0].score * 100)),
        recommendations[1].bundle.name,
        String(Math.round(recommendations[1].score * 100)),
        recommendations[2].bundle.name,
        String(Math.round(recommendations[2].score * 100)),
      ])
      setProgress(Math.round(((index + 1) / msisdns.length) * 100))
      await wait(28)
    }

    const csv = rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `graphsage_predictions_${new Date().toISOString().slice(0, 10)}.csv`
    anchor.click()
    URL.revokeObjectURL(url)
    setExporting(false)
    setSuccess(true)
  }, [bundles, msisdns])

  return (
    <section className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-minteal-100 bg-white/90 p-5 shadow-sm">
          <p className="text-xs uppercase tracking-[0.22em] text-minteal-400">Total MSISDNs</p>
          <p className="mt-2 font-mono text-4xl font-bold text-minteal-950">{msisdns.length.toLocaleString()}</p>
        </div>
        <div className="rounded-2xl border border-minteal-100 bg-white/90 p-5 shadow-sm">
          <p className="text-xs uppercase tracking-[0.22em] text-minteal-400">Predictions per node</p>
          <p className="mt-2 font-mono text-4xl font-bold text-minteal-950">Top 3</p>
        </div>
      </div>
      <div className="rounded-2xl border border-minteal-100 bg-white/90 p-5 shadow-sm">
        <p className="text-xs uppercase tracking-[0.25em] text-minteal-400">Batch export</p>
        <h3 className="mt-2 text-2xl font-bold text-minteal-950">Generate prediction CSV</h3>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-minteal-600">
          Runs the dummy GraphSAGE predictor for every MSISDN node and downloads a timestamped CSV with the top three bundles.
        </p>
        <div className="mt-5 h-3 overflow-hidden rounded-full bg-minteal-100">
          <div className="h-full rounded-full bg-gradient-to-r from-minteal-500 to-minteal-900 transition-all duration-300" style={{ width: `${progress}%` }} />
        </div>
        <div className="mt-2 flex items-center justify-between text-xs text-minteal-500">
          <span>{exporting ? 'Processing subscriber graph...' : success ? 'Export complete' : 'Ready'}</span>
          <span className="font-mono text-minteal-950">{progress}%</span>
        </div>
        <button
          type="button"
          onClick={generateCsv}
          disabled={exporting}
          className="mt-5 inline-flex items-center justify-center gap-2 rounded-xl bg-minteal-900 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-minteal-800 disabled:cursor-wait disabled:bg-minteal-500"
        >
          <ArrowDownTrayIcon className="h-5 w-5" />
          {exporting ? 'Generating...' : 'Generate CSV'}
        </button>
        {success ? (
          <div className="mt-4 inline-flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
            <CheckCircleIcon className="h-5 w-5" />
            CSV downloaded successfully.
          </div>
        ) : null}
      </div>
    </section>
  )
}

const TargetingPage = () => {
  const graph = useMemo(() => createGraphData(), [])
  const [activeTab, setActiveTab] = useState<DashboardTab>('graph')
  const [realGraph, setRealGraph] = useState<RealGraphData>(emptyRealGraph)
  const [selectedNode, setSelectedNode] = useState<RealGraphNode | null>(null)
  const [detailRecommendations, setDetailRecommendations] = useState<GraphSageRecommendation[]>([])
  const [graphLoading, setGraphLoading] = useState(false)
  const [graphError, setGraphError] = useState<string | null>(null)
  const [predicting, setPredicting] = useState(false)
  const [graphStats, setGraphStats] = useState<GraphStatsResponse | null>(null)

  const selectedMsisdn = selectedNode?.type === 'msisdn' ? selectedNode : null

  const loadGraphSample = useCallback(async () => {
    setGraphLoading(true)
    setGraphError(null)
    setDetailRecommendations([])

    try {
      const response = await graphsageApi.getGraphSample(500, 1000, 500)
      const nextGraph = normalizeGraphResponse(response)
      setRealGraph(nextGraph)
      setSelectedNode(nextGraph.nodes.find((node) => node.type === 'msisdn') ?? nextGraph.nodes[0] ?? null)
    } catch (apiError) {
      setRealGraph(emptyRealGraph)
      setSelectedNode(null)
      setGraphError(getApiErrorMessage(apiError))
    } finally {
      setGraphLoading(false)
    }
  }, [])

  const loadNodeNeighborhood = useCallback(async (node: RealGraphNode) => {
    setSelectedNode(node)
    setGraphLoading(true)
    setGraphError(null)
    setDetailRecommendations([])

    try {
      const response =
        node.type === 'msisdn'
          ? await graphsageApi.getMsisdnNeighborhood(node.msisdn ?? node.label, 1000)
          : await graphsageApi.getBundleNeighborhood(node.bundleId ?? node.label, 100)
      const nextGraph = normalizeGraphResponse(response)
      setRealGraph(nextGraph)
      setSelectedNode(nextGraph.nodes.find((item) => item.id === node.id) ?? normalizeSingleGraphNode({
        id: node.id,
        node_type: node.type === 'msisdn' ? 'user' : 'bundle',
        label: node.label,
        features: node.features,
      }))
    } catch (apiError) {
      setGraphError(getApiErrorMessage(apiError))
    } finally {
      setGraphLoading(false)
    }
  }, [])

  const handleGraphSearch = useCallback(async (query: string) => {
    const normalizedQuery = query.trim()
    if (!normalizedQuery) {
      return
    }

    setGraphLoading(true)
    setGraphError(null)
    setDetailRecommendations([])

    try {
      const searchResults = await graphsageApi.searchGraph(normalizedQuery, 'all', 20)
      const first = searchResults.results[0]
      if (!first) {
        setGraphError(`No graph nodes found for "${normalizedQuery}".`)
        return
      }

      const node = normalizeSingleGraphNode(first)
      const response =
        node.type === 'msisdn'
          ? await graphsageApi.getMsisdnNeighborhood(node.msisdn ?? node.label, 1000)
          : await graphsageApi.getBundleNeighborhood(node.bundleId ?? node.label, 100)
      const nextGraph = normalizeGraphResponse(response)
      setRealGraph(nextGraph)
      setSelectedNode(nextGraph.nodes.find((item) => item.id === node.id) ?? node)
    } catch (apiError) {
      setGraphError(getApiErrorMessage(apiError))
    } finally {
      setGraphLoading(false)
    }
  }, [])

  const handlePredict = useCallback(async () => {
    const msisdn = selectedMsisdn?.msisdn ?? selectedMsisdn?.label
    if (!msisdn) {
      return
    }
    setPredicting(true)
    setDetailRecommendations([])
    try {
      const response = await graphsageApi.getRecommendationsByMsisdn(msisdn, 10)
      setDetailRecommendations(response.recommendations)
    } catch (apiError) {
      setGraphError(getApiErrorMessage(apiError))
    } finally {
      setPredicting(false)
    }
  }, [selectedMsisdn])

  useEffect(() => {
    void loadGraphSample()
  }, [loadGraphSample])

  useEffect(() => {
    let ignore = false

    const loadGraphStats = async () => {
      try {
        const stats = await graphsageApi.getGraphStats()
        if (!ignore) {
          setGraphStats(stats)
        }
      } catch {
        if (!ignore) {
          setGraphStats(null)
        }
      }
    }

    void loadGraphStats()

    return () => {
      ignore = true
    }
  }, [])

  const displayedStats = graphStats ?? {
    msisdn_nodes: graph.msisdns.length,
    bundle_nodes: graph.bundles.length,
    total_edges: graph.edges.length,
  }

  return (
    <div className="-m-6 min-h-full bg-gradient-to-b from-white/70 to-minteal-50 text-minteal-900">
      <style>{`
        @keyframes targeting-rise {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes targeting-particle {
          0%, 100% { transform: translate3d(0,0,0); opacity: 0.25; }
          50% { transform: translate3d(10px,-16px,0); opacity: 0.8; }
        }
        .targeting-rise { animation: targeting-rise 520ms ease both; }
        .targeting-particle { animation: targeting-particle 5s ease-in-out infinite; }
      `}</style>
      <div className="min-h-[calc(100vh-73px)]">
        <main className="min-w-0 p-4 lg:p-6">
          <header className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.34em] text-minteal-400">Telecom GraphSAGE Recommendation Dashboard</p>
              <h1 className="mt-2 max-w-4xl text-3xl font-black tracking-tight text-minteal-950 lg:text-4xl">
                Interactive subscriber graph and bundle link prediction
              </h1>
              <div className="mt-4 rounded-2xl border border-minteal-100 bg-white/90 p-2 shadow-sm">
                <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
                  <div className="flex items-center gap-3 rounded-xl bg-minteal-50 px-3 py-3 lg:min-w-56">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-minteal-900 text-white shadow-sm">
                      <CpuChipIcon className="h-6 w-6" />
                    </div>
                    <div>
                      <h2 className="text-sm font-black tracking-tight text-minteal-950">Telecom RecSys</h2>
                      <p className="text-xs uppercase tracking-[0.22em] text-minteal-400">GraphSAGE</p>
                    </div>
                  </div>
                  <nav className="grid flex-1 grid-cols-2 gap-2 xl:grid-cols-4">
                    {navigation.map((item) => {
                      const Icon = item.icon
                      const isActive = activeTab === item.id
                      return (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => setActiveTab(item.id)}
                          className={`relative inline-flex items-center justify-center gap-2 rounded-xl px-3 py-3 text-sm font-semibold transition ${
                            isActive
                              ? 'bg-minteal-900 text-white shadow-sm'
                              : 'text-minteal-600 hover:bg-minteal-50 hover:text-minteal-900'
                          }`}
                        >
                          <Icon className="h-5 w-5 shrink-0" />
                          <span>{item.label}</span>
                          {isActive ? <span className="absolute right-3 top-3 h-2 w-2 rounded-full bg-minteal-200 shadow-[0_0_12px_rgba(147,189,183,0.9)]" /> : null}
                        </button>
                      )
                    })}
                  </nav>
                  <div className="flex items-center justify-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-3 text-xs text-emerald-700 lg:justify-start">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
                    <span>Model online</span>
                  </div>
                </div>
              </div>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-minteal-600">
                Live graph sample, neighborhood search, personalized predictions, cold-start scoring, and batch CSV export.
              </p>
            </div>
            <div className="rounded-2xl border border-minteal-100 bg-white/90 px-4 py-3 text-sm text-minteal-600 shadow-sm backdrop-blur">
              <span className="font-mono text-minteal-950">requestAnimationFrame</span> renderer active
            </div>
          </header>

          <section className="mb-5 grid gap-4 md:grid-cols-3">
            <StatCard icon={UserCircleIcon} label="MSISDN Nodes" value={formatCompactNumber(displayedStats.msisdn_nodes)} tone="bg-minteal-50 text-minteal-700" delay={0} />
            <StatCard icon={CubeTransparentIcon} label="Bundle Nodes" value={formatCompactNumber(displayedStats.bundle_nodes)} tone="bg-minteal-100 text-minteal-800" delay={90} />
            <StatCard icon={SignalIcon} label="Total Edges" value={formatCompactNumber(displayedStats.total_edges)} tone="bg-minteal-50 text-minteal-600" delay={180} />
          </section>

          {activeTab === 'graph' ? (
            <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr),380px]">
              <Graph3D
                graph={realGraph}
                selectedId={selectedNode?.id ?? null}
                onSelect={(node) => {
                  void loadNodeNeighborhood(node)
                }}
                loading={graphLoading}
                error={graphError}
                onSearch={(query) => {
                  void handleGraphSearch(query)
                }}
                onLoadSample={() => {
                  void loadGraphSample()
                }}
              />
              <NodeDetailPanel
                node={selectedNode}
                recommendations={detailRecommendations}
                loading={predicting}
                onPredict={handlePredict}
              />
            </section>
          ) : null}

          {activeTab === 'predictions' ? (
            <PredictionsPanel />
          ) : null}

          {activeTab === 'cold-start' ? <ColdStartPanel /> : null}

          {activeTab === 'export' ? <ExportPanel msisdns={graph.msisdns} bundles={graph.bundles} /> : null}
        </main>
      </div>
    </div>
  )
}

export default TargetingPage
