import { CircleStackIcon, LinkIcon, UserGroupIcon } from '@heroicons/react/24/outline'
import type { GraphSageFeatureOptions } from '../../api/graphsage'

type SummaryStripProps = {
  options: GraphSageFeatureOptions | null
  loading: boolean
  error: string | null
}

const numberFormatter = new Intl.NumberFormat('en-US')

const SummaryItem = ({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: number | null
  icon: typeof UserGroupIcon
}) => (
  <div className="flex min-w-0 items-center gap-3 rounded-xl border border-minteal-100 bg-white px-4 py-3">
    <Icon className="h-5 w-5 shrink-0 text-minteal-600" />
    <div className="min-w-0">
      <p className="text-xs uppercase tracking-[0.2em] text-minteal-400">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums text-minteal-950">
        {value == null ? '--' : numberFormatter.format(value)}
      </p>
    </div>
  </div>
)

const SummaryStrip = ({ options, loading, error }: SummaryStripProps) => (
  <section className="rounded-2xl border border-minteal-100 bg-white/80 p-3 shadow-sm">
    <div className="grid gap-3 md:grid-cols-3">
      <SummaryItem label="Users" value={options?.counts.users ?? null} icon={UserGroupIcon} />
      <SummaryItem label="Bundles" value={options?.counts.bundles ?? null} icon={CircleStackIcon} />
      <SummaryItem label="Train edges" value={options?.counts.train_edges ?? null} icon={LinkIcon} />
    </div>
    {loading ? <p className="mt-3 px-1 text-xs font-medium text-minteal-500">Loading GraphSAGE feature options...</p> : null}
    {error ? <p className="mt-3 px-1 text-xs font-semibold text-rose-700">{error}</p> : null}
  </section>
)

export default SummaryStrip
