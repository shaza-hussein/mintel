import KpiCard from '../components/ui/KpiCard'
import { LoadingState } from '../components/ui/StateMessage'

const ForecastPage = () => (
  <div className="space-y-6">
    <header className="space-y-2">
      <p className="text-xs uppercase tracking-[0.4em] text-minteal-400">Forecasting & analytics</p>
      <h2 className="text-2xl font-semibold text-minteal-900">Predictive insights</h2>
      <p className="text-sm text-minteal-500">
        Clustered forecasts combine churn, usage, and competitive intelligence for the next 90 days.
      </p>
    </header>

    <div className="grid gap-4 md:grid-cols-3">
      <KpiCard label="Revenue outlook" value="+6.8%" delta="+1.1 pts" trend="up" />
      <KpiCard label="Churn delta" value="-3.2%" delta="-0.7 pts" trend="down" />
      <KpiCard label="Upsell readiness" value="74%" delta="+5 pts" trend="up" />
    </div>

    <div className="rounded-2xl border border-minteal-200 bg-white/80 p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-minteal-900">90d forecast band</h3>
        <span className="text-xs text-minteal-400">Projected vs actual</span>
      </div>
      <div className="mt-6 rounded-2xl border border-dashed border-minteal-200 bg-gradient-to-b from-minteal-50 to-white/80 p-12 text-center text-sm text-minteal-400">
        Chart placeholder (analytics overlay will render here)
      </div>
    </div>

    <LoadingState message="Calibrating forecast confidence" />
  </div>
)

export default ForecastPage
