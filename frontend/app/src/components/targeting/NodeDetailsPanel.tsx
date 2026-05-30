import type { GraphLink, GraphNode } from '../../api/graphsage'

export type GraphSelection =
  | {
      kind: 'node'
      item: GraphNode
    }
  | {
      kind: 'edge'
      item: GraphLink
    }

type NodeDetailsPanelProps = {
  selection: GraphSelection | null
}

const formatValue = (value: unknown): string => {
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

const KeyValueRows = ({ values }: { values: Record<string, unknown> }) => {
  const entries = Object.entries(values)

  if (entries.length === 0) {
    return <p className="text-sm text-minteal-500">No features returned for this item.</p>
  }

  return (
    <div className="max-h-[420px] overflow-auto rounded-xl border border-minteal-100">
      <table className="min-w-full divide-y divide-minteal-100 text-sm">
        <tbody className="divide-y divide-minteal-100 bg-white">
          {entries.map(([key, value]) => (
            <tr key={key}>
              <td className="w-44 px-3 py-2 align-top text-xs font-semibold uppercase tracking-[0.16em] text-minteal-400">
                {key}
              </td>
              <td className="px-3 py-2 text-minteal-800">
                <span className="break-words">{formatValue(value)}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const NodeDetailsPanel = ({ selection }: NodeDetailsPanelProps) => {
  if (!selection) {
    return (
      <aside className="rounded-2xl border border-dashed border-minteal-200 bg-white/80 p-5">
        <p className="text-sm font-semibold text-minteal-800">Select a node or link</p>
        <p className="mt-1 text-sm text-minteal-500">Click in the graph to inspect raw identifiers and features.</p>
      </aside>
    )
  }

  if (selection.kind === 'edge') {
    return (
      <aside className="rounded-2xl border border-minteal-100 bg-white p-5 shadow-sm">
        <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Selected link</p>
        <h3 className="mt-2 text-lg font-semibold text-minteal-950">{selection.item.edge_type}</h3>
        <div className="mt-4 grid gap-3 text-sm text-minteal-700">
          <p>
            <span className="font-semibold">Source:</span> {selection.item.source}
          </p>
          <p>
            <span className="font-semibold">Target:</span> {selection.item.target}
          </p>
          <p>
            <span className="font-semibold">Weight:</span> {selection.item.weight.toLocaleString()}
          </p>
        </div>
        <div className="mt-5">
          <KeyValueRows values={selection.item.features} />
        </div>
      </aside>
    )
  }

  return (
    <aside className="rounded-2xl border border-minteal-100 bg-white p-5 shadow-sm">
      <p className="text-xs uppercase tracking-[0.24em] text-minteal-400">Selected {selection.item.node_type}</p>
      <h3 className="mt-2 truncate text-lg font-semibold text-minteal-950" title={selection.item.label}>
        {selection.item.label}
      </h3>
      <div className="mt-4 grid gap-3 text-sm text-minteal-700">
        <p>
          <span className="font-semibold">Raw ID:</span> {selection.item.raw_id}
        </p>
        <p>
          <span className="font-semibold">Index:</span> {selection.item.index}
        </p>
      </div>
      <div className="mt-5">
        <KeyValueRows values={selection.item.features} />
      </div>
    </aside>
  )
}

export default NodeDetailsPanel
