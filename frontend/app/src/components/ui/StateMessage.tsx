export const LoadingState = ({ message = 'Loading telemetry' }: { message?: string }) => (
  <div className="flex flex-col items-center justify-center space-y-2 rounded-2xl border border-dashed border-minteal-200 bg-white/70 p-6 text-sm text-minteal-500">
    <div className="h-8 w-8 animate-spin rounded-full border-2 border-t-minteal-900 border-minteal-300" />
    <p>{message}</p>
  </div>
)

export const ErrorState = ({ message = 'Unable to load data' }: { message?: string }) => (
  <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
    <p className="font-semibold">{message}</p>
    <p className="text-xs text-rose-500">Retry or check telemetry integration</p>
  </div>
)

export const EmptyState = ({ message = 'No items to show' }: { message?: string }) => (
  <div className="rounded-2xl border border-minteal-200 bg-white/80 p-6 text-sm text-minteal-500">
    <p className="font-semibold text-minteal-600">{message}</p>
  </div>
)
