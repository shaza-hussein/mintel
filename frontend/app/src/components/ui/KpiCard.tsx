interface KpiCardProps {
  label: string
  value: string
  delta?: string
  trend?: 'up' | 'down' | 'flat'
  helpers?: string
}

const trendColors = {
  up: 'text-emerald-500',
  down: 'text-rose-500',
  flat: 'text-minteal-500',
}

const KpiCard = ({ label, value, delta, trend = 'flat', helpers }: KpiCardProps) => (
  <div className="min-h-[120px] rounded-2xl border border-minteal-200 bg-white/80 p-4 shadow-sm">
    <p className="text-xs font-semibold uppercase tracking-[0.4em] text-minteal-400">{label}</p>
    <div className="mt-2 flex items-center justify-between gap-4">
      <p className="text-3xl font-semibold text-minteal-900">{value}</p>
      {delta && (
        <span className={`text-sm font-semibold ${trendColors[trend] ?? trendColors.flat}`}>
          {delta}
        </span>
      )}
    </div>
    {helpers && <p className="mt-1 text-xs text-minteal-500">{helpers}</p>}
  </div>
)

export default KpiCard
