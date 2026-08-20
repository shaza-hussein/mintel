import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, MouseEvent as ReactMouseEvent } from 'react'
import { ArrowPathIcon } from '@heroicons/react/24/outline'
import {
  getApiErrorMessage,
  graphsageApi,
  type GraphLink,
  type GraphNode,
  type GraphSageFeatureOptions,
  type GraphVisualizationResponse,
} from '../../api/graphsage'
import { EmptyState, ErrorState, LoadingState } from '../ui/StateMessage'
import NodeDetailsPanel, { type GraphSelection } from './NodeDetailsPanel'

type GraphExplorerProps = {
  options: GraphSageFeatureOptions | null
}

type LayoutNode = GraphNode & {
  x: number
  y: number
  vx: number
  vy: number
}

type TooltipState = {
  x: number
  y: number
  title: string
  rows: Array<[string, string]>
}

const viewBox = {
  width: 1100,
  height: 620,
}

const fieldClassName =
  'mt-2 w-full rounded-xl border border-minteal-200 bg-white px-3 py-2 text-sm font-medium text-minteal-900 outline-none transition focus:border-minteal-500 focus:ring-2 focus:ring-minteal-200'

const numberFormatter = new Intl.NumberFormat('en-US')

const formatValue = (value: unknown) => {
  if (value == null) {
    return 'N/A'
  }

  if (typeof value === 'number') {
    return Number.isFinite(value) ? value.toLocaleString() : 'N/A'
  }

  if (typeof value === 'string' || typeof value === 'boolean') {
    return String(value)
  }

  return JSON.stringify(value)
}

const featureRows = (features: Record<string, unknown>, limit = 4): Array<[string, string]> =>
  Object.entries(features)
    .slice(0, limit)
    .map(([key, value]) => [key, formatValue(value)])

const parseOptionalNumber = (value: string) => {
  const parsed = Number(value)
  return value.trim() !== '' && Number.isFinite(parsed) ? parsed : undefined
}

const initializeLayout = (nodes: GraphNode[]): LayoutNode[] => {
  const userNodes = nodes.filter((node) => node.node_type === 'user')
  const bundleNodes = nodes.filter((node) => node.node_type !== 'user')
  const bundleCount = Math.max(bundleNodes.length, 1)
  const userCount = Math.max(userNodes.length, 1)

  return nodes.map((node) => {
    const collection = node.node_type === 'user' ? userNodes : bundleNodes
    const index = Math.max(collection.findIndex((item) => item.id === node.id), 0)
    const count = node.node_type === 'user' ? userCount : bundleCount
    const angle = (index / count) * Math.PI * 2
    const baseX = node.node_type === 'user' ? viewBox.width * 0.32 : viewBox.width * 0.68
    const radius = node.node_type === 'user' ? 120 : 170

    return {
      ...node,
      x: baseX + Math.cos(angle) * radius,
      y: viewBox.height * 0.5 + Math.sin(angle) * radius,
      vx: 0,
      vy: 0,
    }
  })
}

const runForceTick = (nodes: LayoutNode[], links: GraphLink[]) => {
  const byId = new Map(nodes.map((node) => [node.id, node]))

  nodes.forEach((node) => {
    const targetX = node.node_type === 'user' ? viewBox.width * 0.3 : viewBox.width * 0.7
    const targetY = viewBox.height * 0.5
    node.vx += (targetX - node.x) * 0.002
    node.vy += (targetY - node.y) * 0.002
  })

  const repulsionLimit = Math.min(nodes.length, 420)
  for (let leftIndex = 0; leftIndex < repulsionLimit; leftIndex += 1) {
    const left = nodes[leftIndex]

    for (let rightIndex = leftIndex + 1; rightIndex < repulsionLimit; rightIndex += 1) {
      const right = nodes[rightIndex]
      const dx = left.x - right.x
      const dy = left.y - right.y
      const distanceSquared = Math.max(dx * dx + dy * dy, 80)
      const force = 360 / distanceSquared
      const distance = Math.sqrt(distanceSquared)
      const xForce = (dx / distance) * force
      const yForce = (dy / distance) * force

      left.vx += xForce
      left.vy += yForce
      right.vx -= xForce
      right.vy -= yForce
    }
  }

  links.forEach((link) => {
    const source = byId.get(link.source)
    const target = byId.get(link.target)

    if (!source || !target) {
      return
    }

    const dx = target.x - source.x
    const dy = target.y - source.y
    const distance = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
    const desired = 145
    const force = (distance - desired) * 0.004
    const xForce = (dx / distance) * force
    const yForce = (dy / distance) * force

    source.vx += xForce
    source.vy += yForce
    target.vx -= xForce
    target.vy -= yForce
  })

  nodes.forEach((node) => {
    node.vx *= 0.82
    node.vy *= 0.82
    node.x = Math.max(28, Math.min(viewBox.width - 28, node.x + node.vx))
    node.y = Math.max(28, Math.min(viewBox.height - 28, node.y + node.vy))
  })
}

const GraphCanvas = ({
  graph,
  onSelect,
}: {
  graph: GraphVisualizationResponse
  onSelect: (selection: GraphSelection) => void
}) => {
  const wrapperRef = useRef<HTMLDivElement | null>(null)
  const [layout, setLayout] = useState<LayoutNode[]>([])
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  useEffect(() => {
    const nodes = initializeLayout(graph.nodes)
    let frame = 0
    let ticks = 0

    setLayout(nodes.map((node) => ({ ...node })))

    const animate = () => {
      runForceTick(nodes, graph.links)
      ticks += 1

      if (ticks % 2 === 0) {
        setLayout(nodes.map((node) => ({ ...node })))
      }

      if (ticks < 180) {
        frame = window.requestAnimationFrame(animate)
      }
    }

    frame = window.requestAnimationFrame(animate)

    return () => {
      window.cancelAnimationFrame(frame)
    }
  }, [graph])

  const layoutById = useMemo(() => new Map(layout.map((node) => [node.id, node])), [layout])

  const updateTooltip = (event: ReactMouseEvent<SVGElement>, title: string, rows: Array<[string, string]>) => {
    const bounds = wrapperRef.current?.getBoundingClientRect()

    if (!bounds) {
      return
    }

    setTooltip({
      x: event.clientX - bounds.left + 14,
      y: event.clientY - bounds.top + 14,
      title,
      rows,
    })
  }

  if (graph.nodes.length === 0 || graph.links.length === 0) {
    return <EmptyState message="No graph nodes or links returned for the current filters." />
  }

  return (
    <div ref={wrapperRef} className="relative h-[640px] overflow-hidden rounded-2xl border border-minteal-100 bg-white">
      <svg
        viewBox={`0 0 ${viewBox.width} ${viewBox.height}`}
        className="h-full w-full touch-none"
        role="img"
        aria-label="User bundle recommendation graph"
        onMouseLeave={() => setTooltip(null)}
      >
        <rect width={viewBox.width} height={viewBox.height} fill="#ffffff" />
        {graph.links.map((link, index) => {
          const source = layoutById.get(link.source)
          const target = layoutById.get(link.target)

          if (!source || !target) {
            return null
          }

          const strokeWidth = Math.max(1, Math.min(7, Math.sqrt(Math.max(link.weight, 1))))

          return (
            <line
              key={`${link.source}-${link.target}-${index}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke="#8aa7a6"
              strokeOpacity={0.34}
              strokeWidth={strokeWidth}
              className="cursor-pointer transition hover:stroke-minteal-800"
              onClick={() => onSelect({ kind: 'edge', item: link })}
              onMouseMove={(event) =>
                updateTooltip(event, `${link.source} to ${link.target}`, [
                  ['type', link.edge_type],
                  ['weight', formatValue(link.weight)],
                  ...featureRows(link.features, 3),
                ])
              }
            />
          )
        })}

        {layout.map((node) => {
          const isUser = node.node_type === 'user'
          const rows: Array<[string, string]> = [
            ['type', node.node_type],
            ['raw_id', node.raw_id],
            ...featureRows(node.features, 4),
          ]

          if (isUser) {
            return (
              <circle
                key={node.id}
                cx={node.x}
                cy={node.y}
                r={9}
                fill="#0f766e"
                stroke="#ffffff"
                strokeWidth={2}
                className="cursor-pointer drop-shadow-sm"
                onClick={() => onSelect({ kind: 'node', item: node })}
                onMouseMove={(event) => updateTooltip(event, node.label, rows)}
              />
            )
          }

          return (
            <rect
              key={node.id}
              x={node.x - 8}
              y={node.y - 8}
              width={16}
              height={16}
              rx={3}
              fill="#2563eb"
              stroke="#ffffff"
              strokeWidth={2}
              className="cursor-pointer drop-shadow-sm"
              transform={`rotate(45 ${node.x} ${node.y})`}
              onClick={() => onSelect({ kind: 'node', item: node })}
              onMouseMove={(event) => updateTooltip(event, node.label, rows)}
            />
          )
        })}
      </svg>

      <div className="pointer-events-none absolute bottom-4 left-4 flex flex-wrap gap-3 rounded-xl border border-minteal-100 bg-white/92 px-3 py-2 text-xs font-semibold text-minteal-700 shadow-sm">
        <span className="inline-flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-teal-700" />
          Users
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="h-3 w-3 rotate-45 rounded-[3px] bg-blue-600" />
          Bundles
        </span>
      </div>

      {tooltip ? (
        <div
          className="pointer-events-none absolute z-20 max-w-xs rounded-xl border border-minteal-100 bg-white px-3 py-2 text-xs shadow-xl"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <p className="truncate font-semibold text-minteal-950">{tooltip.title}</p>
          <div className="mt-2 space-y-1 text-minteal-600">
            {tooltip.rows.map(([key, value]) => (
              <p key={`${key}-${value}`} className="grid grid-cols-[84px,1fr] gap-2">
                <span className="font-semibold text-minteal-400">{key}</span>
                <span className="truncate">{value}</span>
              </p>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}

const GraphExplorer = ({ options }: GraphExplorerProps) => {
  const priceRange = options?.numeric_ranges.price
  const bundleTypeOptions = options?.bundle_features.bundle_type.values ?? []
  const [maxEdges, setMaxEdges] = useState('500')
  const [msisdn, setMsisdn] = useState('')
  const [bundleType, setBundleType] = useState('')
  const [minPrice, setMinPrice] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [graph, setGraph] = useState<GraphVisualizationResponse | null>(null)
  const [selection, setSelection] = useState<GraphSelection | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!priceRange) {
      return
    }

    setMinPrice((current) => current || String(priceRange.min))
    setMaxPrice((current) => current || String(priceRange.max))
  }, [priceRange])

  const fetchGraph = async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await graphsageApi.getGraphVisualization({
        max_edges: Math.max(1, Number(maxEdges) || 500),
        bundle_type: bundleType || undefined,
        msisdn: msisdn || undefined,
        min_price: parseOptionalNumber(minPrice),
        max_price: parseOptionalNumber(maxPrice),
      })
      setGraph(data)
      setSelection(null)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchGraph()
  }, [])

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void fetchGraph()
  }

  const summary = graph?.summary

  return (
    <div className="space-y-5">
      <form onSubmit={handleSubmit} className="rounded-2xl border border-minteal-100 bg-white/90 p-5 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end">
          <label htmlFor="graph-max-edges" className="block min-w-[140px] flex-1 text-sm font-medium text-minteal-700">
            Max edges
            <input
              id="graph-max-edges"
              type="number"
              min={1}
              value={maxEdges}
              onChange={(event) => setMaxEdges(event.target.value)}
              className={fieldClassName}
            />
          </label>
          <label htmlFor="graph-msisdn" className="block min-w-[180px] flex-1 text-sm font-medium text-minteal-700">
            MSISDN filter
            <input
              id="graph-msisdn"
              value={msisdn}
              onChange={(event) => setMsisdn(event.target.value)}
              placeholder="Optional"
              className={fieldClassName}
            />
          </label>
          <label htmlFor="graph-bundle-type" className="block min-w-[190px] flex-1 text-sm font-medium text-minteal-700">
            Bundle type
            <select
              id="graph-bundle-type"
              value={bundleType}
              onChange={(event) => setBundleType(event.target.value)}
              className={fieldClassName}
            >
              <option value="">All bundle types</option>
              {bundleTypeOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="graph-min-price" className="block min-w-[130px] flex-1 text-sm font-medium text-minteal-700">
            Min price
            <input
              id="graph-min-price"
              type="number"
              value={minPrice}
              onChange={(event) => setMinPrice(event.target.value)}
              className={fieldClassName}
            />
          </label>
          <label htmlFor="graph-max-price" className="block min-w-[130px] flex-1 text-sm font-medium text-minteal-700">
            Max price
            <input
              id="graph-max-price"
              type="number"
              value={maxPrice}
              onChange={(event) => setMaxPrice(event.target.value)}
              className={fieldClassName}
            />
          </label>
          <button
            type="submit"
            disabled={loading}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-minteal-900 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-minteal-800 disabled:cursor-not-allowed disabled:bg-minteal-400"
          >
            <ArrowPathIcon className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </form>

      {summary ? (
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          {[
            ['Nodes', summary.node_count],
            ['Links', summary.link_count],
            ['Users', summary.user_count],
            ['Bundles', summary.bundle_count],
            ['Returned', summary.returned_edges],
            ['Available', summary.available_edges_after_filters],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl border border-minteal-100 bg-white px-4 py-3">
              <p className="text-xs uppercase tracking-[0.18em] text-minteal-400">{label}</p>
              <p className="mt-1 text-lg font-semibold text-minteal-950">{numberFormatter.format(Number(value))}</p>
            </div>
          ))}
        </div>
      ) : null}

      {error ? <ErrorState message={error} /> : null}
      {loading && !graph ? <LoadingState message="Loading graph visualization" /> : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr),360px]">
        <div>{graph && !loading ? <GraphCanvas graph={graph} onSelect={setSelection} /> : null}</div>
        <NodeDetailsPanel selection={selection} />
      </div>
    </div>
  )
}

export default GraphExplorer
