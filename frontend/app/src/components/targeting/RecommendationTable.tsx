import type { Recommendation } from '../../api/graphsage'

type RecommendationTableProps = {
  recommendations: Recommendation[]
  showExplanation?: boolean
}

const numberFormatter = new Intl.NumberFormat('en-US')

const scoreToPercent = (score: number) => {
  if (!Number.isFinite(score)) {
    return 0
  }

  return Math.max(0, Math.min(100, score <= 1 ? score * 100 : score))
}

const formatScore = (score: number) => (Number.isFinite(score) ? score.toFixed(3) : '0.000')

const formatPrice = (price: number) => (Number.isFinite(price) ? numberFormatter.format(price) : '0')

const Badge = ({ children }: { children: string }) => (
  <span className="inline-flex max-w-full items-center rounded-full border border-minteal-200 bg-minteal-50 px-2.5 py-1 text-xs font-semibold text-minteal-700">
    <span className="truncate">{children}</span>
  </span>
)

const RecommendationTable = ({ recommendations, showExplanation = false }: RecommendationTableProps) => {
  if (recommendations.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-minteal-200 bg-white p-5 text-sm font-medium text-minteal-500">
        No recommendations returned.
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-xl border border-minteal-100 bg-white">
      <div className="max-h-[560px] overflow-auto">
        <table className="min-w-full table-fixed divide-y divide-minteal-100 text-left text-sm">
          <thead className="sticky top-0 z-10 bg-minteal-50 text-xs uppercase tracking-[0.18em] text-minteal-500">
            <tr>
              <th className="w-16 px-4 py-3 font-semibold">Rank</th>
              <th className="w-[28%] px-4 py-3 font-semibold">Bundle</th>
              <th className="w-36 px-4 py-3 font-semibold">Type</th>
              <th className="w-28 px-4 py-3 font-semibold">Price</th>
              <th className="w-40 px-4 py-3 font-semibold">Score</th>
              <th className="w-40 px-4 py-3 font-semibold">Method</th>
              {showExplanation ? <th className="w-[24%] px-4 py-3 font-semibold">Explanation</th> : null}
            </tr>
          </thead>
          <tbody className="divide-y divide-minteal-100 text-minteal-900">
            {recommendations.map((recommendation) => {
              const scorePercent = scoreToPercent(recommendation.score)

              return (
                <tr key={`${recommendation.msisdn}-${recommendation.bundle_id}-${recommendation.rank}`} className="hover:bg-minteal-50/70">
                  <td className="px-4 py-3 font-semibold text-minteal-700">{recommendation.rank}</td>
                  <td className="px-4 py-3">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-minteal-950" title={recommendation.bundle_name}>
                        {recommendation.bundle_name || recommendation.bundle_id}
                      </p>
                      <p className="truncate text-xs text-minteal-500" title={recommendation.bundle_id}>
                        {recommendation.bundle_id}
                      </p>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge>{recommendation.bundle_type || 'Unknown'}</Badge>
                  </td>
                  <td className="px-4 py-3 font-medium">{formatPrice(recommendation.price)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="h-2 w-20 overflow-hidden rounded-full bg-minteal-100">
                        <div className="h-full rounded-full bg-minteal-700" style={{ width: `${scorePercent}%` }} />
                      </div>
                      <span className="tabular-nums text-minteal-700">{formatScore(recommendation.score)}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge>{recommendation.recommendation_type || 'graphsage'}</Badge>
                  </td>
                  {showExplanation ? (
                    <td className="px-4 py-3 text-xs leading-5 text-minteal-600">
                      {recommendation.matched_features && recommendation.matched_features.length > 0 ? (
                        <p className="line-clamp-2" title={recommendation.matched_features.join(', ')}>
                          {recommendation.matched_features.join(', ')}
                        </p>
                      ) : (
                        <p>No matched features returned</p>
                      )}
                      <p className="mt-1 font-semibold text-minteal-800">
                        Cohort: {recommendation.cohort_size == null ? 'N/A' : recommendation.cohort_size.toLocaleString()}
                      </p>
                    </td>
                  ) : null}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default RecommendationTable
