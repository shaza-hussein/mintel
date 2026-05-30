import { EmptyState, LoadingState } from '../components/ui/StateMessage'

const CampaignSimulationPage = () => (
  <div className="space-y-6">
    <header className="space-y-2">
      <p className="text-xs uppercase tracking-[0.4em] text-minteal-400">Campaign simulation</p>
      <h2 className="text-2xl font-semibold text-minteal-900">Impact preview</h2>
    </header>
    <div className="grid gap-4 lg:grid-cols-[2fr,1fr]">
      <div className="rounded-2xl border border-minteal-200 bg-white/80 p-6 shadow-sm">
        <p className="text-sm text-minteal-500">
          Simulated campaign lift will be available once the sales intent feeds are refreshed. Queue length is
          currently under review.
        </p>
        <div className="mt-6 space-y-2 text-sm text-minteal-600">
          <p className="text-minteal-500">Channels: Digital, call center, field</p>
          <p className="text-minteal-500">Budget cap: $420k</p>
          <p className="text-minteal-500">Target segments: Premium households, SMB edge</p>
        </div>
      </div>
      <LoadingState message="Running baseline simulations" />
    </div>
    <EmptyState message="No campaign snapshots yet (sync telemetry > 10s)" />
  </div>
)

export default CampaignSimulationPage
