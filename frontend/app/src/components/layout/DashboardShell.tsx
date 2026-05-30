import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import {
  HomeIcon,
  CubeTransparentIcon,
  BoltIcon,
  CursorArrowRaysIcon,
  UserGroupIcon,
  PresentationChartBarIcon,
} from '@heroicons/react/24/outline'

const navLinks = [
  { name: 'Executive Dashboard', path: '/', icon: HomeIcon },
  { name: 'AI Bundle Studio', path: '/bundle', icon: CubeTransparentIcon },
  { name: 'AI Pricing', path: '/pricing', icon: BoltIcon },
  { name: 'Campaign Simulation', path: '/campaign', icon: CursorArrowRaysIcon },
  { name: 'Targeting & Personalization', path: '/targeting', icon: UserGroupIcon },
  { name: 'Forecasting & Analytics', path: '/forecast', icon: PresentationChartBarIcon },
]

const DashboardShell = ({ children }: { children: ReactNode }) => {
  return (
    <div className="min-h-screen bg-minteal-50 text-minteal-900">
      <div className="flex h-screen">
        <aside className="flex w-72 flex-col bg-minteal-900 text-white">
          <div className="px-6 py-6">
            <p className="text-sm uppercase tracking-[0.3em] text-minteal-300">MinTel</p>
            <h1 className="mt-2 text-2xl font-semibold">MinTel</h1>
            <p className="text-sm text-minteal-200">Mind of Telecom Operator</p>
          </div>
          <nav className="flex flex-1 flex-col gap-1 px-4">
            {navLinks.map((link) => (
              <NavLink
                to={link.path}
                key={link.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition-colors hover:bg-minteal-700 ${
                    isActive ? 'bg-white/10 text-white shadow-lg shadow-black/20' : 'text-minteal-200'
                  }`
                }
              >
                <link.icon className="h-5 w-5" />
                <span className="truncate">{link.name}</span>
              </NavLink>
            ))}
          </nav>
          <div className="px-6 py-4 text-xs text-minteal-200">
            <p>Last synced 12s ago</p>
            <p>Region: EMEA - MinTel v4.2</p>
          </div>
        </aside>
        <div className="flex flex-1 flex-col overflow-hidden">
          <header className="border-b border-minteal-100 bg-white/80 px-6 py-4 backdrop-blur">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.4em] text-minteal-500">Live state</p>
                <h2 className="text-xl font-semibold text-minteal-900">Operational scenario: Fusion Tone</h2>
              </div>
              <div className="flex items-center gap-3">
                <button className="rounded-full border border-minteal-200 px-4 py-2 text-sm font-medium text-minteal-600 hover:border-minteal-400">
                  Scenario Compare
                </button>
                <button className="rounded-full bg-minteal-900 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-minteal-900/30">
                  Trigger Simulation
                </button>
              </div>
            </div>
          </header>
          <main className="flex-1 overflow-auto bg-gradient-to-b from-white/70 to-minteal-50 px-6 py-6">
            {children}
          </main>
        </div>
      </div>
    </div>
  )
}

export default DashboardShell
