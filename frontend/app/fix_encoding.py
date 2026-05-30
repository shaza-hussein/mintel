from pathlib import Path
files = [
    'src/App.tsx',
    'src/components/layout/DashboardShell.tsx',
    'src/components/ui/KpiCard.tsx',
    'src/components/ui/StateMessage.tsx',
    'src/data/mockResponses.ts',
    'src/services/minTelApi.ts',
    'src/types/api.ts',
    'src/pages/DashboardPage.tsx',
    'src/pages/BundleGenerationPage.tsx',
    'src/pages/PricingEnginePage.tsx',
    'src/pages/CampaignSimulationPage.tsx',
    'src/pages/TargetingPage.tsx',
    'src/pages/ForecastPage.tsx',
    'src/styles/index.css',
]
for path in files:
    p = Path(path)
    text = p.read_text(encoding='utf-8-sig')
    p.write_text(text, encoding='utf-8')
