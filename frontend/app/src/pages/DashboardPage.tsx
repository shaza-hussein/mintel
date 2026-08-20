import KpiCard from '../components/ui/KpiCard'
import { LoadingState } from '../components/ui/StateMessage'

const kpis = [
  {
    label: 'Average Revenue per User',
    value: '$152',
    delta: '+7.3%',
    trend: 'up' as const,
    helpers: 'rolling 30d vs. prior 30d',
  },
  {
    label: 'Churn risk flagged',
    value: '18k',
    delta: '-12%',
    trend: 'down' as const,
    helpers: 'bot-classified roaming accounts',
  },
  {
    label: 'AI NPS uplift',
    value: '+9 pts',
    delta: '+2 pts',
    trend: 'up' as const,
    helpers: 'next-gen plan pilots',
  },
]

const alerts = [
  'Next-gen bundling automation completed 4m ago',
  'Customer support queue < 12 active cases',
  'Data ingestion lag 0.4s (within SLA)',
]

const DashboardPage = () => (
  <div className="space-y-8">
    <section className="rounded-2xl border border-minteal-200 bg-white/80 p-6 shadow-sm">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.4em] text-minteal-400">Executive summary</p>
          <h2 className="text-2xl font-semibold text-minteal-900">Mission control</h2>
        </div>
        <div className="text-sm text-minteal-500">Last refreshed 12s ago</div>
      </div>
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} {...kpi} />
        ))}
      </div>
    </section>

    <section className="grid gap-4 lg:grid-cols-[2fr,1fr]">
      <div className="rounded-2xl border border-minteal-200 bg-white/80 p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-semibold text-minteal-900">Telemetry & ops</h3>
          <span className="text-xs uppercase tracking-[0.4em] text-minteal-400">Live</span>
        </div>
        <div className="mt-4 space-y-3 text-sm text-minteal-600">
          {alerts.map((alert) => (
            <p key={alert} className="rounded-xl border border-dashed border-minteal-200 px-4 py-3 bg-minteal-50">
              {alert}
            </p>
          ))}
        </div>
      </div>
      <LoadingState message="Streaming telemetry from next-gen core" />
    </section>
  </div>
)

export default DashboardPage
