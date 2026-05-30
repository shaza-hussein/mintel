import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  AdjustmentsHorizontalIcon,
  ArrowTrendingUpIcon,
  MegaphoneIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import KpiCard from '../ui/KpiCard'

type Option = { key: string; title: string; description: string; accentClassName?: string }

type Props = {
  form: { audience: string; strategy: string; channel: string; priceCeiling: number; dataPriority: number; loyaltyWeight: number; roaming: boolean; entertainment: boolean; multiSim: boolean }
  result: {
    bundleName: string
    tagline: string
    heroMessage: string
    audienceLabel: string
    audienceSummary: string
    channelNarrative: string
    price: number
    dataGb: number
    generatedTakeUp: number
    adoptionLift: number
    arpuLift: number
    churnReduction: number
    npsLift: number
    incrementalRevenue: number
    marginAfterPromo: number
    launchReadiness: number
    marketFit: number
    paybackMonths: number
    addressableBase: string
    components: Array<{ label: string; value: string; accentClassName: string }>
    highlights: string[]
    processSteps: Array<{ title: string; kicker: string; score: number; insight: string; detail: string; chips: string[]; accentClassName: string }>
    rampData: Array<{ period: string; baseline: number; generated: number; revenue: number }>
    launchPlan: Array<{ phase: string; window: string; action: string; kpi: string }>
    messageFrames: string[]
  }
  generatedAt: string
  generationCount: number
  activePresetKey: string
  presetOptions: Option[]
  audienceOptions: Option[]
  strategyOptions: Option[]
  channelOptions: Option[]
  selectedAudience: { label: string; summary: string }
  selectedStrategy: { label: string; description: string }
  selectedChannel: { label: string; launchLabel: string }
  onPresetSelect: (key: string) => void
  onAudienceSelect: (key: string) => void
  onStrategySelect: (key: string) => void
  onChannelSelect: (key: string) => void
  onPriceCeilingChange: (value: number) => void
  onDataPriorityChange: (value: number) => void
  onLoyaltyWeightChange: (value: number) => void
  onEntertainmentToggle: () => void
  onRoamingToggle: () => void
  onMultiSimToggle: () => void
  onGenerate: () => void
}

const panel = 'rounded-[2rem] border border-minteal-100 bg-white/90 shadow-[0_28px_70px_-42px_rgba(12,27,27,0.28)]'
const muted = 'rounded-[1.6rem] border border-minteal-100 bg-minteal-50/75'
const ink = '#0c1b1b'
const grid = '#dbe5e5'
const text = '#4c7c7c'
const mint = '#14b8a6'
const gold = '#f59e0b'
const money = (value: number) => `$${value.toFixed(0)}`
const millions = (value: number) => `$${value.toFixed(1)}M`
const levels = ['Very low', 'Low', 'Balanced', 'High', 'Very high']

const Section = ({ eyebrow, title, description }: { eyebrow: string; title: string; description?: string }) => (
  <div>
    <p className="text-xs uppercase tracking-[0.35em] text-minteal-400">{eyebrow}</p>
    <h3 className="mt-2 text-2xl font-semibold text-minteal-900">{title}</h3>
    {description ? <p className="mt-2 text-sm leading-7 text-minteal-500">{description}</p> : null}
  </div>
)

const Card = ({ active, title, description, onClick, accentClassName }: { active: boolean; title: string; description: string; onClick: () => void; accentClassName?: string }) => (
  <button type="button" aria-pressed={active} onClick={onClick} className={`rounded-[1.3rem] border p-4 text-left transition ${active ? accentClassName ?? 'border-minteal-900 bg-minteal-900 text-white shadow-lg shadow-minteal-900/15' : 'border-minteal-100 bg-white text-minteal-900 hover:border-minteal-300'}`}>
    <p className="text-sm font-semibold">{title}</p>
    <p className={`mt-1 text-xs leading-5 ${active ? 'text-white/75' : 'text-minteal-500'}`}>{description}</p>
  </button>
)

const Toggle = ({ active, title, description, onClick }: { active: boolean; title: string; description: string; onClick: () => void }) => (
  <button type="button" aria-pressed={active} onClick={onClick} className={`rounded-[1.4rem] border p-4 text-left transition ${active ? 'border-minteal-900 bg-minteal-900 text-white shadow-lg shadow-minteal-900/10' : 'border-minteal-100 bg-white text-minteal-900 hover:border-minteal-300'}`}>
    <p className="text-sm font-semibold">{title}</p>
    <p className={`mt-1 text-xs leading-5 ${active ? 'text-white/75' : 'text-minteal-500'}`}>{description}</p>
  </button>
)

const Slider = ({ label, value, display, hint, min, max, onChange }: { label: string; value: number; display: string; hint: string; min: number; max: number; onChange: (value: number) => void }) => (
  <label className={`${muted} block p-4`}>
    <div className="flex items-center justify-between gap-4">
      <div><span className="text-sm font-semibold text-minteal-900">{label}</span><p className="mt-1 text-xs text-minteal-500">{hint}</p></div>
      <span className="rounded-full bg-white px-3 py-1 text-sm font-semibold text-minteal-900">{display}</span>
    </div>
    <input type="range" min={min} max={max} step={1} value={value} onChange={(event) => onChange(Number(event.target.value))} className="mt-4 w-full accent-minteal-900" />
  </label>
)

const Stat = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-[1.4rem] border border-minteal-100 bg-minteal-50/80 p-4">
    <p className="text-[11px] uppercase tracking-[0.3em] text-minteal-400">{label}</p>
    <p className="mt-2 text-2xl font-semibold text-minteal-900">{value}</p>
  </div>
)

const Row = ({ label, value, helper }: { label: string; value: string; helper?: string }) => (
  <div className="flex flex-col gap-2 rounded-[1.2rem] bg-white px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
    <div><p className="text-xs uppercase tracking-[0.18em] text-minteal-400">{label}</p>{helper ? <p className="mt-1 text-xs leading-5 text-minteal-500">{helper}</p> : null}</div>
    <p className="text-sm font-semibold text-minteal-900 sm:max-w-[45%] sm:text-right">{value}</p>
  </div>
)

const BundleGenerationSimpleView = ({ form, result, generatedAt, generationCount, activePresetKey, presetOptions, audienceOptions, strategyOptions, channelOptions, selectedAudience, selectedStrategy, selectedChannel, onPresetSelect, onAudienceSelect, onStrategySelect, onChannelSelect, onPriceCeilingChange, onDataPriorityChange, onLoyaltyWeightChange, onEntertainmentToggle, onRoamingToggle, onMultiSimToggle, onGenerate }: Props) => {
  const activeAddOns = [form.entertainment ? 'Entertainment pass' : null, form.roaming ? 'Roaming boost' : null, form.multiSim ? 'Shared lines' : null].filter((item): item is string => Boolean(item))
  const steps = result.processSteps.slice(0, 3)
  const plan = result.launchPlan.slice(0, 3)
  const lead = result.components[0]
  const support = result.components[result.components.length - 1]
  const versions = generationCount === 1 ? '1 version created in this session' : `${generationCount} versions created in this session`

  return (
    <div className="space-y-6">
      <section className={`${panel} overflow-hidden`}>
        <div className="grid gap-0 xl:grid-cols-[360px,minmax(0,1fr)]">
          <aside className="border-b border-minteal-100 bg-[linear-gradient(180deg,_rgba(248,250,252,0.96)_0%,_rgba(240,253,250,0.95)_100%)] p-6 xl:sticky xl:top-6 xl:h-fit xl:border-b-0 xl:border-r">
            <div className="flex items-start justify-between gap-4"><Section eyebrow="Bundle Builder" title="Create a clear bundle brief" description="Pick the audience, goal, and channel, then tune a few inputs." /><AdjustmentsHorizontalIcon className="h-11 w-11 rounded-2xl bg-white p-2.5 text-minteal-700 shadow-sm" /></div>
            <div className="mt-6 space-y-6">
              <div><p className="text-sm font-semibold text-minteal-900">Preset</p><div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">{presetOptions.map((option) => <Card key={option.key} active={activePresetKey === option.key} title={option.title} description={option.description} accentClassName={option.accentClassName} onClick={() => onPresetSelect(option.key)} />)}</div></div>
              <div><p className="text-sm font-semibold text-minteal-900">Audience</p><div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">{audienceOptions.map((option) => <Card key={option.key} active={form.audience === option.key} title={option.title} description={option.description} onClick={() => onAudienceSelect(option.key)} />)}</div></div>
              <div><p className="text-sm font-semibold text-minteal-900">Goal</p><div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">{strategyOptions.map((option) => <Card key={option.key} active={form.strategy === option.key} title={option.title} description={option.description} onClick={() => onStrategySelect(option.key)} />)}</div></div>
              <div><p className="text-sm font-semibold text-minteal-900">Launch channel</p><div className="mt-3 grid gap-3">{channelOptions.map((option) => <Card key={option.key} active={form.channel === option.key} title={option.title} description={option.description} onClick={() => onChannelSelect(option.key)} />)}</div></div>
              <div className="grid gap-3">
                <Slider label="Max price" value={form.priceCeiling} display={money(form.priceCeiling)} hint="Highest monthly price for the offer." min={24} max={90} onChange={onPriceCeilingChange} />
                <Slider label="Data focus" value={form.dataPriority} display={levels[form.dataPriority - 1] ?? `${form.dataPriority}`} hint="How strongly the bundle should lean into data." min={1} max={5} onChange={onDataPriorityChange} />
                <Slider label="Loyalty focus" value={form.loyaltyWeight} display={levels[form.loyaltyWeight - 1] ?? `${form.loyaltyWeight}`} hint="How much retention should shape the offer." min={1} max={5} onChange={onLoyaltyWeightChange} />
              </div>
              <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
                <Toggle active={form.entertainment} title="Entertainment pass" description={form.entertainment ? 'Include content value.' : 'No content add-on.'} onClick={onEntertainmentToggle} />
                <Toggle active={form.roaming} title="Roaming boost" description={form.roaming ? 'Add travel utility.' : 'Keep it local-first.'} onClick={onRoamingToggle} />
                <Toggle active={form.multiSim} title="Shared lines" description={form.multiSim ? 'Support family or multi-line selling.' : 'Single-line focus.'} onClick={onMultiSimToggle} />
              </div>
              <div className={`${muted} p-4`}>
                <p className="text-xs uppercase tracking-[0.25em] text-minteal-400">Brief summary</p>
                <div className="mt-4 space-y-3">
                  <Row label="Audience" value={selectedAudience.label} helper={selectedAudience.summary} />
                  <Row label="Goal" value={selectedStrategy.label} helper={selectedStrategy.description} />
                  <Row label="Channel" value={selectedChannel.label} helper={selectedChannel.launchLabel} />
                </div>
                <div className="mt-4 flex flex-wrap gap-2"><span className="rounded-full bg-white px-3 py-2 text-xs font-semibold text-minteal-700">Price cap {money(form.priceCeiling)}</span>{activeAddOns.length > 0 ? activeAddOns.map((item) => <span key={item} className="rounded-full bg-white px-3 py-2 text-xs font-semibold text-minteal-700">{item}</span>) : <span className="rounded-full bg-white px-3 py-2 text-xs font-semibold text-minteal-500">No add-ons selected</span>}</div>
              </div>
              <button type="button" onClick={onGenerate} className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-minteal-900 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-minteal-900/20 transition hover:bg-minteal-800"><SparklesIcon className="h-5 w-5" />Generate bundle</button>
            </div>
          </aside>
          <div className="space-y-6 p-6 lg:p-8">
            <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr),280px]">
              <div className="overflow-hidden rounded-[2rem] border border-minteal-100 bg-[linear-gradient(135deg,_rgba(236,253,245,0.92)_0%,_rgba(255,255,255,0.98)_52%,_rgba(224,242,254,0.92)_100%)] p-6 lg:p-8">
                <p className="text-xs uppercase tracking-[0.35em] text-minteal-500">Recommended bundle</p>
                <h2 className="mt-3 max-w-4xl text-3xl font-semibold leading-tight text-minteal-900 sm:text-4xl">{result.bundleName}</h2>
                <p className="mt-4 max-w-3xl text-base leading-7 text-minteal-600">{result.tagline}</p>
                <div className="mt-6 grid gap-3 sm:grid-cols-3"><Stat label="Price" value={money(result.price)} /><Stat label="Data" value={`${result.dataGb}GB`} /><Stat label="Take-up lift" value={`+${result.adoptionLift} pts`} /></div>
                <div className="mt-6 rounded-[1.6rem] border border-minteal-100 bg-white/80 p-5 shadow-sm"><p className="text-xs uppercase tracking-[0.25em] text-minteal-400">Why this bundle is easy to understand</p><p className="mt-3 text-sm leading-7 text-minteal-700 sm:text-base">{result.heroMessage}</p><div className="mt-5 grid gap-3 sm:grid-cols-2">{result.highlights.slice(0, 4).map((highlight) => <div key={highlight} className="rounded-[1.3rem] border border-minteal-100 bg-minteal-50/70 p-4 text-sm leading-6 text-minteal-700">{highlight}</div>)}</div></div>
              </div>
              <div className="space-y-4">
                <Stat label="Forecast take-up" value={`${result.generatedTakeUp}%`} />
                <Stat label="90-day revenue" value={millions(result.incrementalRevenue)} />
                <Stat label="Market fit" value={`${result.marketFit}%`} />
                <Stat label="Launch readiness" value={`${result.launchReadiness}%`} />
                <div className={`${muted} p-4`}><p className="text-xs uppercase tracking-[0.25em] text-minteal-400">Latest run</p><p className="mt-2 text-lg font-semibold text-minteal-900">{generatedAt}</p><p className="mt-1 text-sm leading-6 text-minteal-500">{versions}</p></div>
              </div>
            </section>
            <section className="grid gap-6 lg:grid-cols-[0.95fr,1.05fr]">
              <div className={`${panel} p-6`}>
                <Section eyebrow="Bundle details" title="What is inside the offer" description="Keep the sales story short and clear." />
                <div className="mt-6 grid gap-3">{result.components.map((component) => <div key={component.label} className="flex flex-col gap-3 rounded-[1.4rem] border border-minteal-100 bg-minteal-50/70 p-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-semibold text-minteal-900">{component.label}</p><p className="mt-1 text-xs leading-5 text-minteal-500">Use this as a main proof point.</p></div><span className={`w-fit rounded-full px-3 py-2 text-xs font-semibold ring-1 ${component.accentClassName}`}>{component.value}</span></div>)}</div>
              </div>
              <div className={`${panel} p-6`}>
                <div className="flex items-start justify-between gap-4"><Section eyebrow="Plain-language brief" title="What the team should say" description="A short handoff for marketing and sales." /><MegaphoneIcon className="h-11 w-11 rounded-2xl bg-cyan-100 p-2.5 text-cyan-700" /></div>
                <div className="mt-6 space-y-4">
                  <div className={`${muted} p-4`}><p className="text-xs uppercase tracking-[0.25em] text-minteal-400">Target audience</p><p className="mt-2 text-lg font-semibold text-minteal-900">{result.audienceLabel}</p><p className="mt-2 text-sm leading-6 text-minteal-600">{result.audienceSummary}</p></div>
                  <div className={`${muted} p-4`}><p className="text-xs uppercase tracking-[0.25em] text-minteal-400">Launch channel</p><p className="mt-2 text-lg font-semibold text-minteal-900">{selectedChannel.label}</p><p className="mt-2 text-sm leading-6 text-minteal-600">{result.channelNarrative}</p></div>
                  <div className="rounded-[1.5rem] bg-minteal-900 p-5 text-white"><p className="text-xs uppercase tracking-[0.25em] text-white/60">Best opening line</p><p className="mt-3 text-lg font-semibold">{result.messageFrames[0]}</p><p className="mt-3 text-sm leading-6 text-white/75">Open with {lead ? lead.value : `${result.dataGb}GB`} and back it up with {support ? support.value.toLowerCase() : 'a simple bonus'}.</p></div>
                </div>
              </div>
            </section>
          </div>
        </div>
      </section>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Take-up lift" value={`+${result.adoptionLift} pts`} delta={`${result.generatedTakeUp}% forecast`} trend="up" helpers="versus the current bundle baseline" />
        <KpiCard label="ARPU uplift" value={`+${result.arpuLift}%`} delta={`${result.marginAfterPromo}% margin`} trend="up" helpers="expected value expansion" />
        <KpiCard label="Churn reduction" value={`-${result.churnReduction} pts`} delta={`${result.npsLift} NPS pts`} trend="up" helpers="retention effect after launch" />
        <KpiCard label="90d revenue" value={millions(result.incrementalRevenue)} delta={`${result.paybackMonths}m payback`} trend="up" helpers="incremental contribution forecast" />
      </section>
      <section className="grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
        <div className={`${panel} p-6`}>
          <div className="flex items-start justify-between gap-4"><Section eyebrow="Performance view" title="Expected lift over the current plan" description="A single chart to compare the generated bundle with the baseline." /><ArrowTrendingUpIcon className="h-11 w-11 rounded-2xl bg-minteal-100 p-2.5 text-minteal-700" /></div>
          <div className="mt-6 h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={result.rampData} margin={{ top: 12, right: 24, bottom: 8, left: 0 }}>
                <defs><linearGradient id="simpleBundleRamp" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={mint} stopOpacity={0.78} /><stop offset="100%" stopColor={mint} stopOpacity={0.08} /></linearGradient></defs>
                <CartesianGrid stroke={grid} vertical={false} />
                <XAxis dataKey="period" tickLine={false} axisLine={false} tick={{ fill: text, fontSize: 12 }} />
                <YAxis yAxisId="left" tickLine={false} axisLine={false} tick={{ fill: text, fontSize: 12 }} />
                <YAxis yAxisId="right" orientation="right" tickLine={false} axisLine={false} tick={{ fill: text, fontSize: 12 }} />
                <Tooltip contentStyle={{ backgroundColor: 'rgba(255,255,255,0.97)', border: '1px solid #dbe5e5', borderRadius: '18px' }} labelStyle={{ color: ink }} />
                <Area yAxisId="left" type="monotone" dataKey="generated" stroke={ink} fill="url(#simpleBundleRamp)" strokeWidth={3} />
                <Line yAxisId="left" type="monotone" dataKey="baseline" stroke="#94a3b8" strokeWidth={2.5} />
                <Line yAxisId="right" type="monotone" dataKey="revenue" stroke={gold} strokeWidth={3} dot={{ r: 4, fill: gold }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className={`${panel} overflow-hidden`}>
          <div className="bg-[linear-gradient(135deg,_rgba(12,27,27,0.98)_0%,_rgba(18,54,54,0.98)_48%,_rgba(15,118,110,0.92)_100%)] p-6 text-white"><p className="text-xs uppercase tracking-[0.35em] text-white/60">Launch plan</p><h3 className="mt-2 text-2xl font-semibold text-white">What to do next</h3><p className="mt-2 text-sm leading-7 text-white/70">A short rollout plan, core message, and commercial guardrails.</p></div>
          <div className="space-y-6 p-6">
            <div className="grid gap-4">{steps.map((step) => <article key={step.title} className={`rounded-[1.6rem] border border-minteal-100 bg-gradient-to-br ${step.accentClassName} p-5`}><div className="flex items-center justify-between gap-4"><div><p className="text-xs uppercase tracking-[0.25em] text-minteal-500">{step.kicker}</p><h4 className="mt-2 text-lg font-semibold text-minteal-900">{step.title}</h4></div><span className="rounded-full bg-white px-4 py-2 text-sm font-semibold text-minteal-900 shadow-sm">{step.score}%</span></div><p className="mt-4 text-sm font-medium leading-6 text-minteal-800">{step.insight}</p><p className="mt-2 text-sm leading-6 text-minteal-600">{step.detail}</p></article>)}</div>
            <div className="grid gap-3">{plan.map((item) => <article key={item.phase} className={`${muted} p-4`}><div className="flex items-center justify-between gap-4"><p className="text-sm font-semibold text-minteal-900">{item.phase}</p><span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-minteal-600">{item.window}</span></div><p className="mt-3 text-sm leading-6 text-minteal-600">{item.action}</p><p className="mt-3 text-xs font-semibold uppercase tracking-[0.2em] text-minteal-500">{item.kpi}</p></article>)}</div>
            <div className={`${muted} p-4`}><p className="text-xs uppercase tracking-[0.25em] text-minteal-400">Commercial guardrails</p><div className="mt-4 space-y-3"><Row label="Payback" value={`${result.paybackMonths} months`} helper="Time to recover launch investment." /><Row label="Margin" value={`${result.marginAfterPromo}%`} helper="Expected margin after promotional support." /><Row label="Addressable base" value={result.addressableBase} helper="Estimated lines in scope for the chosen audience." /></div></div>
          </div>
        </div>
      </section>
    </div>
  )
}

export default BundleGenerationSimpleView
