import { Navigate, Route, Routes } from 'react-router-dom'
import DashboardShell from './components/layout/DashboardShell'
import DashboardPage from './pages/DashboardPage'
import BundleGenerationPage from './pages/BundleGenerationPage'
import PricingEnginePage from './pages/PricingEnginePage'
import CampaignSimulationPage from './pages/CampaignSimulationPage'
import TargetingPage from './pages/TargetingPage'
import ForecastPage from './pages/ForecastPage'

function App() {
  return (
    <DashboardShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/bundle" element={<BundleGenerationPage />} />
        <Route path="/pricing" element={<PricingEnginePage />} />
        <Route path="/campaign" element={<CampaignSimulationPage />} />
        <Route path="/targeting" element={<TargetingPage />} />
        <Route path="/forecast" element={<ForecastPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </DashboardShell>
  )
}

export default App
