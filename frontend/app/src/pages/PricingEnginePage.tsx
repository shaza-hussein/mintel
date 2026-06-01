import { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import type { EChartsOption, SeriesOption } from 'echarts'
import ReactECharts from 'echarts-for-react'
import { ArrowPathIcon, CalculatorIcon, CurrencyDollarIcon } from '@heroicons/react/24/outline'
import { ErrorState, LoadingState } from '../components/ui/StateMessage'

type ServiceKey = 'voice' | 'data' | 'sms'
type OfferType =
  | 'atl'
  | 'diy_mode'
  | 'promotion_mode'
  | 'btl_normal'
  | 'btl_moderate'
  | 'btl_aggressive'

type Point = [number, number]

type ServiceConfig = {
  anchor_price: number
  anchor_rate: number
  floor_rate: number
  max_price: number
  unit_name: string
  daily_points?: Point[]
  weekly_points?: Point[]
  decay_k: number | null
}

type PromotionConfig = {
  starting_price: number
  ending_price: number
  discount: number
  validity: number
}

type PricingConfig = {
  services: Record<ServiceKey, ServiceConfig>
  validity_premiums: Record<string, number>
  mixed_bundle_discounts: Record<string, number>
  btl_discounts: Record<OfferType, number>
  rounding_rules: {
    data_round_to: number
  }
  minimums: {
    price: Record<ServiceKey, number>
    volume: Record<ServiceKey, number>
    multi_service_volume: Record<ServiceKey, number>
  }
  promotion_mode_param: Record<ServiceKey, PromotionConfig>
}

type BundleResponse = {
  units: Record<string, string>
}

type PriceLookupResponse = {
  calculated_price: number
  individual_prices?: Record<string, number> | null
}

type ConfigResponse = {
  config: PricingConfig
}

type ChartTooltipParam = {
  seriesName?: string
  marker?: string
  value?: [number, number, number | null, string | null]
}

type PlotlyChartTrace = {
  type?: string
  mode?: string
  name?: string
  x?: number[]
  y?: number[]
  text?: string[]
  textposition?: string
  showlegend?: boolean
  line?: {
    color?: string
    width?: number
    dash?: string
  }
  marker?: {
    color?: string
    size?: number
    symbol?: string
    line?: {
      color?: string
      width?: number
    }
  }
  customdata?: Array<[number, string]>
}

type PlotlyChartShape = {
  type?: string
  xref?: string
  yref?: string
  x0?: number
  x1?: number
  y0?: number
  y1?: number
  opacity?: number
  line?: {
    color?: string
    width?: number
    dash?: string
  }
}

type PlotlyChartAnnotation = {
  text?: string
  y?: number
}

type PlotlyChartLayout = {
  title?: string | { text?: string }
  xaxis?: { title?: string | { text?: string } }
  yaxis?: { title?: string | { text?: string } }
  shapes?: PlotlyChartShape[]
  annotations?: PlotlyChartAnnotation[]
}

type PricingVisualizationChart = {
  service: ServiceKey
  data: PlotlyChartTrace[]
  layout: PlotlyChartLayout
  meta?: {
    unit_name?: string
    floor_rate?: number
  }
}

type PricingVisualizationResponse = {
  charts: Partial<Record<ServiceKey, PricingVisualizationChart>>
}

type BundleFormState = {
  voice: string
  data: string
  sms: string
  customValidity: string
  standardValidity: number
  offerType: OfferType
}

type LookupFormState = {
  voice: string
  data: string
  sms: string
  customValidity: string
  standardValidity: number
  offerType: OfferType
}

type ConfigFormState = {
  services: {
    voice: { anchorPrice: number; anchorRate: number; floorRate: number }
    data: { anchorPrice: number; anchorRate: number; floorRate: number }
    sms: { anchorPrice: number; anchorRate: number; floorRate: number }
  }
  validityPremiums: {
    day2: number
    day3: number
    day7: number
    day30: number
  }
  discounts: {
    mix2: number
    mix3: number
    btlNormal: number
    btlModerate: number
    btlAggressive: number
  }
  promotion: Record<ServiceKey, PromotionConfig>
}

const API_BASE_URL =
  (import.meta.env.VITE_PRICING_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ??
  'http://127.0.0.1:8000'

const SERVICE_LABELS: Record<ServiceKey, string> = {
  voice: 'Voice',
  data: 'Data',
  sms: 'SMS',
}

const OFFER_TYPE_OPTIONS: Array<{ value: OfferType; label: string }> = [
  { value: 'atl', label: 'ATL (Standard)' },
  { value: 'diy_mode', label: 'DIY Mode' },
  { value: 'promotion_mode', label: 'Promotion Mode' },
  { value: 'btl_normal', label: 'BTL Normal' },
  { value: 'btl_moderate', label: 'BTL Moderate' },
  { value: 'btl_aggressive', label: 'BTL Aggressive' },
]

const VALIDITY_OPTIONS = [1, 2, 3, 7, 30]

const DEFAULT_CONFIG: PricingConfig = {
  services: {
    voice: {
      anchor_price: 200,
      anchor_rate: 13.3,
      floor_rate: 6,
      max_price: 10000,
      unit_name: 'Minutes',
      daily_points: [
        [100, 20],
        [150, 16.67],
        [175, 15.91],
        [200, 12.5],
        [220, 12.22],
        [230, 12.11],
        [300, 10.71],
        [450, 8.82],
        [540, 8.44],
        [750, 7.14],
        [800, 6.67],
      ],
      weekly_points: [
        [300, 18.75],
        [420, 14],
        [525, 12.21],
        [650, 10.83],
        [750, 10],
        [840, 9.13],
        [935, 8.9],
        [1650, 7.5],
        [3520, 7.04],
        [5000, 6.25],
        [5390, 6.19],
      ],
      decay_k: null,
    },
    data: {
      anchor_price: 650,
      anchor_rate: 0.42,
      floor_rate: 0.2,
      max_price: 10000,
      unit_name: 'MB',
      daily_points: [
        [100, 2],
        [190, 1.583],
        [220, 1.294],
        [290, 1.16],
        [650, 0.42],
      ],
      decay_k: null,
    },
    sms: {
      anchor_price: 50,
      anchor_rate: 1.3,
      floor_rate: 0.2,
      max_price: 500,
      unit_name: 'SMS',
      decay_k: null,
    },
  },
  validity_premiums: { 1: 0, 2: 25, 3: 50, 7: 120, 30: 235 },
  mixed_bundle_discounts: { 1: 0, 2: 10, 3: 20 },
  btl_discounts: {
    atl: 0,
    diy_mode: -5,
    promotion_mode: 0,
    btl_normal: 20,
    btl_moderate: 30,
    btl_aggressive: 40,
  },
  rounding_rules: { data_round_to: 5 },
  minimums: {
    price: { voice: 100, data: 100, sms: 0 },
    volume: { voice: 5, data: 50, sms: 0 },
    multi_service_volume: { voice: 5, data: 50, sms: 0 },
  },
  promotion_mode_param: {
    voice: { starting_price: 150, ending_price: 2000, discount: 35, validity: -1 },
    data: { starting_price: 0, ending_price: 0, discount: 0, validity: -1 },
    sms: { starting_price: 0, ending_price: 0, discount: 0, validity: -1 },
  },
}

const DEFAULT_BUNDLE_FORM: BundleFormState = {
  voice: '',
  data: '',
  sms: '',
  customValidity: '',
  standardValidity: 1,
  offerType: 'atl',
}

const DEFAULT_LOOKUP_FORM: LookupFormState = {
  voice: '',
  data: '',
  sms: '',
  customValidity: '',
  standardValidity: 1,
  offerType: 'atl',
}

const DEFAULT_CONFIG_FORM: ConfigFormState = {
  services: {
    voice: { anchorPrice: 200, anchorRate: 13.3, floorRate: 6 },
    data: { anchorPrice: 650, anchorRate: 0.42, floorRate: 0.2 },
    sms: { anchorPrice: 50, anchorRate: 1.3, floorRate: 0.2 },
  },
  validityPremiums: {
    day2: 25,
    day3: 50,
    day7: 120,
    day30: 235,
  },
  discounts: {
    mix2: 10,
    mix3: 20,
    btlNormal: 20,
    btlModerate: 30,
    btlAggressive: 40,
  },
  promotion: {
    voice: { starting_price: 150, ending_price: 2000, discount: 35, validity: -1 },
    data: { starting_price: 0, ending_price: 0, discount: 0, validity: -1 },
    sms: { starting_price: 0, ending_price: 0, discount: 0, validity: -1 },
  },
}

const pricingConfigToFormState = (config: PricingConfig): ConfigFormState => ({
  services: {
    voice: {
      anchorPrice: config.services.voice.anchor_price,
      anchorRate: config.services.voice.anchor_rate,
      floorRate: config.services.voice.floor_rate,
    },
    data: {
      anchorPrice: config.services.data.anchor_price,
      anchorRate: config.services.data.anchor_rate,
      floorRate: config.services.data.floor_rate,
    },
    sms: {
      anchorPrice: config.services.sms.anchor_price,
      anchorRate: config.services.sms.anchor_rate,
      floorRate: config.services.sms.floor_rate,
    },
  },
  validityPremiums: {
    day2: config.validity_premiums['2'] ?? 0,
    day3: config.validity_premiums['3'] ?? 0,
    day7: config.validity_premiums['7'] ?? 0,
    day30: config.validity_premiums['30'] ?? 0,
  },
  discounts: {
    mix2: config.mixed_bundle_discounts['2'] ?? 0,
    mix3: config.mixed_bundle_discounts['3'] ?? 0,
    btlNormal: config.btl_discounts.btl_normal ?? 0,
    btlModerate: config.btl_discounts.btl_moderate ?? 0,
    btlAggressive: config.btl_discounts.btl_aggressive ?? 0,
  },
  promotion: {
    voice: config.promotion_mode_param.voice,
    data: config.promotion_mode_param.data,
    sms: config.promotion_mode_param.sms,
  },
})

const recalculateDecay = (
  anchorPrice: number,
  anchorRate: number,
  floorRate: number,
  maxPrice: number,
) => {
  if (anchorRate <= floorRate || maxPrice <= anchorPrice) {
    return null
  }

  const rateAtMax = floorRate + 0.01
  const numerator = Math.log((rateAtMax - floorRate) / (anchorRate - floorRate))
  const denominator = maxPrice - anchorPrice

  return -numerator / denominator
}

const formatChartNumber = (value: number) =>
  new Intl.NumberFormat('en-US', {
    maximumFractionDigits: value >= 100 ? 0 : 4,
  }).format(value)

const stripChartHtml = (value: string) =>
  value
    .replace(/<br\s*\/?>/gi, ' - ')
    .replace(/<[^>]*>/g, '')
    .replace(/\s+/g, ' ')
    .trim()

const getPlotlyTitleText = (title: string | { text?: string } | undefined) => {
  if (typeof title === 'string') {
    return stripChartHtml(title)
  }

  return stripChartHtml(title?.text ?? '')
}

const normalizeCurrencyLabel = (value: string) => value.replaceAll('NGN', 'Fr')

const getAxisTitleText = (axis: { title?: string | { text?: string } } | undefined) => {
  const title = axis?.title
  const text = typeof title === 'string' ? title : title?.text ?? ''

  return normalizeCurrencyLabel(stripChartHtml(text))
}

const toEChartsLineType = (dash?: string): 'solid' | 'dashed' | 'dotted' => {
  if (dash === 'dash') {
    return 'dashed'
  }

  if (dash === 'dot') {
    return 'dotted'
  }

  return 'solid'
}

const toEChartsSymbol = (symbol?: string) => {
  if (symbol === 'diamond') {
    return 'diamond'
  }

  return 'circle'
}

const formatPricingTooltip = (params: unknown) => {
  const items = Array.isArray(params) ? (params as ChartTooltipParam[]) : [params as ChartTooltipParam]

  return items
    .filter((item) => Array.isArray(item.value))
    .map((item) => {
      const [price, rate, vpm, rule] = item.value ?? [0, 0, null, null]

      const lines = [
        `<strong>${item.marker ?? ''}${item.seriesName ?? ''}</strong>`,
        `Price: Fr ${formatChartNumber(price)}`,
        `Effective rate: ${formatChartNumber(rate)}`,
      ]

      if (typeof vpm === 'number') {
        lines.push(`Validity multiplier: ${vpm.toFixed(2)}x`)
      }

      if (rule) {
        lines.push(`Rule: ${rule}`)
      }

      return lines.join('<br />')
    })
    .join('<br /><br />')
}

const buildTraceSeries = (trace: PlotlyChartTrace): SeriesOption | null => {
  const prices = trace.x ?? []
  const rates = trace.y ?? []

  if (prices.length === 0 || rates.length === 0) {
    return null
  }

  const data = prices.map((price, index) => {
    const custom = trace.customdata?.[index]

    return [price, rates[index], custom?.[0] ?? null, custom?.[1] ?? null]
  })

  if (trace.mode?.includes('lines')) {
    return {
      name: trace.name,
      type: 'line',
      smooth: true,
      showSymbol: false,
      data,
      lineStyle: {
        color: trace.line?.color,
        width: trace.line?.width ?? 3,
        type: toEChartsLineType(trace.line?.dash),
      },
      itemStyle: { color: trace.line?.color },
      emphasis: { focus: 'series' },
    }
  }

  return {
    name: trace.showlegend === false ? undefined : trace.name,
    type: 'scatter',
    symbol: toEChartsSymbol(trace.marker?.symbol),
    symbolSize: trace.marker?.size ?? 9,
    data,
    itemStyle: {
      color: trace.marker?.color,
      borderColor: trace.marker?.line?.color,
      borderWidth: trace.marker?.line?.width,
    },
    label: trace.text?.length
      ? {
          show: true,
          formatter: ({ dataIndex }: { dataIndex: number }) => trace.text?.[dataIndex] ?? '',
          position: 'top',
          color: '#153f3b',
          fontSize: 11,
          fontWeight: 600,
        }
      : undefined,
  }
}

const buildShapeGuideSeries = (chart: PricingVisualizationChart): SeriesOption[] =>
  (chart.layout.shapes ?? [])
    .map<SeriesOption | null>((shape) => {
      if (shape.type !== 'line') {
        return null
      }

      const isVertical = shape.x0 === shape.x1 && typeof shape.x0 === 'number'
      const isHorizontal = shape.y0 === shape.y1 && typeof shape.y0 === 'number'

      if (!isVertical && !isHorizontal) {
        return null
      }

      const annotation = isHorizontal
        ? chart.layout.annotations?.find((item) => item.y === shape.y0)
        : undefined

      return {
        name: undefined,
        type: 'scatter',
        data: [],
        silent: true,
        symbolSize: 0,
        markLine: {
          symbol: 'none',
          label: {
            show: Boolean(annotation?.text),
            formatter: annotation?.text,
            color: '#153f3b',
            fontSize: 11,
            fontWeight: 600,
          },
          lineStyle: {
            color: shape.line?.color ?? '#111827',
            width: shape.line?.width ?? 1,
            type: toEChartsLineType(shape.line?.dash),
            opacity: shape.opacity ?? 1,
          },
          data: [isVertical ? { xAxis: shape.x0 } : { yAxis: shape.y0 }],
        },
      }
    })
    .filter((item): item is SeriesOption => item !== null)

const buildPricingChartOption = (chart: PricingVisualizationChart): EChartsOption => {
  const traceSeries = chart.data
    .map(buildTraceSeries)
    .filter((item): item is SeriesOption => item !== null)
  const shapeSeries = buildShapeGuideSeries(chart)
  const titleText = getPlotlyTitleText(chart.layout.title).split(' - ')[0]

  return {
    backgroundColor: 'transparent',
    title: {
      text: titleText || `${SERVICE_LABELS[chart.service]} Pricing Algorithm Curve`,
      subtext: 'Solid = interpolation | Dashed = decay | Dots = anchor points | Dashed guide = floor',
      left: 0,
      top: 0,
      textStyle: {
        color: '#134e4a',
        fontSize: 18,
        fontWeight: 700,
      },
      subtextStyle: {
        color: '#5f7f7a',
        fontSize: 12,
      },
    },
    grid: {
      top: 100,
      right: 34,
      bottom: 78,
      left: 60,
      containLabel: true,
    },
    legend: {
      type: 'scroll',
      top: 48,
      left: 0,
      right: 0,
      itemWidth: 18,
      itemHeight: 10,
      textStyle: {
        color: '#315c57',
        fontSize: 11,
      },
    },
    tooltip: {
      trigger: 'item',
      formatter: formatPricingTooltip,
      confine: true,
      borderColor: '#ccfbf1',
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      textStyle: {
        color: '#153f3b',
      },
    },
    xAxis: {
      type: 'value',
      name: getAxisTitleText(chart.layout.xaxis),
      nameLocation: 'middle',
      nameGap: 34,
      axisLine: { lineStyle: { color: '#9bbab5' } },
      axisLabel: {
        color: '#4f6f6a',
        formatter: (value: number) => formatChartNumber(value),
      },
      splitLine: { lineStyle: { color: '#eef7f5' } },
    },
    yAxis: {
      type: 'value',
      name: getAxisTitleText(chart.layout.yaxis),
      nameLocation: 'middle',
      nameGap: 52,
      axisLine: { lineStyle: { color: '#9bbab5' } },
      axisLabel: {
        color: '#4f6f6a',
      },
      splitLine: { lineStyle: { color: '#eef7f5' } },
    },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: 0,
        filterMode: 'none',
      },
      {
        type: 'slider',
        height: 18,
        bottom: 18,
        borderColor: '#d9efeb',
        fillerColor: 'rgba(20, 184, 166, 0.18)',
        handleStyle: {
          color: '#0f766e',
        },
      },
    ],
    series: [...traceSeries, ...shapeSeries],
  }
}

const parsePositiveNumberMap = (values: Record<ServiceKey, string>) =>
  (Object.entries(values) as Array<[ServiceKey, string]>).reduce<Partial<Record<ServiceKey, number>>>(
    (acc, [service, value]) => {
      const parsed = Number(value)
      if (!Number.isNaN(parsed) && parsed > 0) {
        acc[service] = parsed
      }
      return acc
    },
    {},
  )

const getErrorMessage = (error: unknown) => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
    return error.message
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Unexpected error'
}

const fieldClassName =
  'mt-2 w-full rounded-xl border border-minteal-200 bg-white px-3 py-2 text-sm text-minteal-900 shadow-sm outline-none transition focus:border-minteal-500 focus:ring-2 focus:ring-minteal-200'

const resultCardClassName = 'rounded-3xl p-6 text-white shadow-lg shadow-minteal-900/15'

const PricingEnginePage = () => {
  const [bundleForm, setBundleForm] = useState(DEFAULT_BUNDLE_FORM)
  const [lookupForm, setLookupForm] = useState(DEFAULT_LOOKUP_FORM)
  const [configForm, setConfigForm] = useState(DEFAULT_CONFIG_FORM)
  const [baseConfig, setBaseConfig] = useState<PricingConfig>(DEFAULT_CONFIG)
  const [configLoading, setConfigLoading] = useState(true)
  const [configError, setConfigError] = useState<string | null>(null)

  const [bundleResult, setBundleResult] = useState<BundleResponse | null>(null)
  const [bundleError, setBundleError] = useState<string | null>(null)
  const [bundleLoading, setBundleLoading] = useState(false)

  const [lookupResult, setLookupResult] = useState<PriceLookupResponse | null>(null)
  const [lookupError, setLookupError] = useState<string | null>(null)
  const [lookupLoading, setLookupLoading] = useState(false)

  const [visualizationCharts, setVisualizationCharts] = useState<Partial<Record<ServiceKey, PricingVisualizationChart>>>({})
  const [visualizationError, setVisualizationError] = useState<string | null>(null)
  const [visualizationLoading, setVisualizationLoading] = useState(true)

  useEffect(() => {
    let isMounted = true

    const loadConfig = async () => {
      setConfigLoading(true)
      setConfigError(null)

      try {
        const { data } = await axios.get<ConfigResponse>(`${API_BASE_URL}/pricing/config`)
        if (!isMounted) {
          return
        }

        setBaseConfig(data.config)
        setConfigForm(pricingConfigToFormState(data.config))
      } catch (error) {
        if (!isMounted) {
          return
        }

        setConfigError(`Using fallback config. ${getErrorMessage(error)}`)
        setBaseConfig(DEFAULT_CONFIG)
        setConfigForm(pricingConfigToFormState(DEFAULT_CONFIG))
      } finally {
        if (isMounted) {
          setConfigLoading(false)
        }
      }
    }

    void loadConfig()

    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    let isMounted = true

    const loadVisualizations = async () => {
      setVisualizationLoading(true)
      setVisualizationError(null)

      try {
        const { data } = await axios.get<PricingVisualizationResponse>(
          `${API_BASE_URL}/pricing/visualization?n_points=400`,
        )

        if (!isMounted) {
          return
        }

        setVisualizationCharts(data.charts)
      } catch (error) {
        if (!isMounted) {
          return
        }

        setVisualizationError(getErrorMessage(error))
      } finally {
        if (isMounted) {
          setVisualizationLoading(false)
        }
      }
    }

    void loadVisualizations()

    return () => {
      isMounted = false
    }
  }, [])

  const pricingConfig = useMemo<PricingConfig>(() => {
    const voiceDecay = recalculateDecay(
      configForm.services.voice.anchorPrice,
      configForm.services.voice.anchorRate,
      configForm.services.voice.floorRate,
      baseConfig.services.voice.max_price,
    )
    const dataDecay = recalculateDecay(
      configForm.services.data.anchorPrice,
      configForm.services.data.anchorRate,
      configForm.services.data.floorRate,
      baseConfig.services.data.max_price,
    )
    const smsDecay = recalculateDecay(
      configForm.services.sms.anchorPrice,
      configForm.services.sms.anchorRate,
      configForm.services.sms.floorRate,
      baseConfig.services.sms.max_price,
    )

    return {
      services: {
        voice: {
          ...baseConfig.services.voice,
          anchor_price: configForm.services.voice.anchorPrice,
          anchor_rate: configForm.services.voice.anchorRate,
          floor_rate: configForm.services.voice.floorRate,
          decay_k: voiceDecay,
        },
        data: {
          ...baseConfig.services.data,
          anchor_price: configForm.services.data.anchorPrice,
          anchor_rate: configForm.services.data.anchorRate,
          floor_rate: configForm.services.data.floorRate,
          decay_k: dataDecay,
        },
        sms: {
          ...baseConfig.services.sms,
          anchor_price: configForm.services.sms.anchorPrice,
          anchor_rate: configForm.services.sms.anchorRate,
          floor_rate: configForm.services.sms.floorRate,
          decay_k: smsDecay,
        },
      },
      validity_premiums: {
        1: 0,
        2: configForm.validityPremiums.day2,
        3: configForm.validityPremiums.day3,
        7: configForm.validityPremiums.day7,
        30: configForm.validityPremiums.day30,
      },
      mixed_bundle_discounts: {
        1: 0,
        2: configForm.discounts.mix2,
        3: configForm.discounts.mix3,
      },
      btl_discounts: {
        atl: 0,
        diy_mode: -5,
        promotion_mode: 0,
        btl_normal: configForm.discounts.btlNormal,
        btl_moderate: configForm.discounts.btlModerate,
        btl_aggressive: configForm.discounts.btlAggressive,
      },
      rounding_rules: baseConfig.rounding_rules,
      minimums: baseConfig.minimums,
      promotion_mode_param: configForm.promotion,
    }
  }, [baseConfig, configForm])

  const decayValues = useMemo(
    () => ({
      voice: pricingConfig.services.voice.decay_k,
      data: pricingConfig.services.data.decay_k,
      sms: pricingConfig.services.sms.decay_k,
    }),
    [pricingConfig],
  )

  const bundleTotalPrice = useMemo(() => {
    const allocations = parsePositiveNumberMap({
      voice: bundleForm.voice,
      data: bundleForm.data,
      sms: bundleForm.sms,
    })

    return Object.values(allocations).reduce((sum, value) => sum + value, 0)
  }, [bundleForm])

  const pricingChartOptions = useMemo(
    () =>
      (['voice', 'data', 'sms'] as ServiceKey[])
        .map((service) => {
          const chart = visualizationCharts[service]

          if (!chart) {
            return null
          }

          return {
            service,
            option: buildPricingChartOption(chart),
          }
        })
        .filter((item): item is { service: ServiceKey; option: EChartsOption } => item !== null),
    [visualizationCharts],
  )

  const updateBundleField = <K extends keyof BundleFormState>(field: K, value: BundleFormState[K]) => {
    setBundleForm((current) => ({ ...current, [field]: value }))
  }

  const updateLookupField = <K extends keyof LookupFormState>(field: K, value: LookupFormState[K]) => {
    setLookupForm((current) => ({ ...current, [field]: value }))
  }

  const updateServiceConfigField = (
    service: ServiceKey,
    field: keyof ConfigFormState['services'][ServiceKey],
    value: number,
  ) => {
    setConfigForm((current) => ({
      ...current,
      services: {
        ...current.services,
        [service]: {
          ...current.services[service],
          [field]: value,
        },
      },
    }))
  }

  const updateValidityField = (
    field: keyof ConfigFormState['validityPremiums'],
    value: number,
  ) => {
    setConfigForm((current) => ({
      ...current,
      validityPremiums: {
        ...current.validityPremiums,
        [field]: value,
      },
    }))
  }

  const updateDiscountField = (field: keyof ConfigFormState['discounts'], value: number) => {
    setConfigForm((current) => ({
      ...current,
      discounts: {
        ...current.discounts,
        [field]: value,
      },
    }))
  }

  const updatePromotionField = (
    service: ServiceKey,
    field: keyof PromotionConfig,
    value: number,
  ) => {
    setConfigForm((current) => ({
      ...current,
      promotion: {
        ...current.promotion,
        [service]: {
          ...current.promotion[service],
          [field]: value,
        },
      },
    }))
  }

  const resetAll = () => {
    setBundleForm(DEFAULT_BUNDLE_FORM)
    setLookupForm(DEFAULT_LOOKUP_FORM)
    setConfigForm(pricingConfigToFormState(baseConfig))
    setBundleResult(null)
    setLookupResult(null)
    setBundleError(null)
    setLookupError(null)
  }

  const handleBundleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setBundleError(null)
    setBundleResult(null)

    const serviceAllocations = parsePositiveNumberMap({
      voice: bundleForm.voice,
      data: bundleForm.data,
      sms: bundleForm.sms,
    })

    if (Object.keys(serviceAllocations).length === 0) {
      setBundleError('Enter at least one price allocation.')
      return
    }

    if (serviceAllocations.voice !== undefined && serviceAllocations.voice < pricingConfig.minimums.price.voice) {
      setBundleError(`Voice price must be at least ${pricingConfig.minimums.price.voice}.`)
      return
    }

    if (serviceAllocations.data !== undefined && serviceAllocations.data < pricingConfig.minimums.price.data) {
      setBundleError(`Data price must be at least ${pricingConfig.minimums.price.data}.`)
      return
    }

    const customValidity = Number(bundleForm.customValidity)
    const validityDays =
      bundleForm.customValidity.trim() !== '' && !Number.isNaN(customValidity)
        ? customValidity
        : bundleForm.standardValidity

    setBundleLoading(true)

    try {
      const { data } = await axios.post<BundleResponse>(`${API_BASE_URL}/pricing/bundle`, {
        service_allocations: serviceAllocations,
        validity_days: validityDays,
        offer_type: bundleForm.offerType,
        config: pricingConfig,
      })

      setBundleResult(data)
    } catch (error) {
      setBundleError(getErrorMessage(error))
    } finally {
      setBundleLoading(false)
    }
  }

  const handleLookupSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setLookupError(null)
    setLookupResult(null)

    const targetVolumes = parsePositiveNumberMap({
      voice: lookupForm.voice,
      data: lookupForm.data,
      sms: lookupForm.sms,
    })

    if (Object.keys(targetVolumes).length === 0) {
      setLookupError('Enter at least one target volume.')
      return
    }

    if (targetVolumes.voice !== undefined && targetVolumes.voice < pricingConfig.minimums.volume.voice) {
      setLookupError(`Voice minutes must be at least ${pricingConfig.minimums.volume.voice}.`)
      return
    }

    if (targetVolumes.data !== undefined && targetVolumes.data < pricingConfig.minimums.volume.data) {
      setLookupError(`Data MB must be at least ${pricingConfig.minimums.volume.data}.`)
      return
    }

    const customValidity = Number(lookupForm.customValidity)
    const validityDays =
      lookupForm.customValidity.trim() !== '' && !Number.isNaN(customValidity)
        ? customValidity
        : lookupForm.standardValidity

    setLookupLoading(true)

    try {
      const { data } = await axios.post<PriceLookupResponse>(`${API_BASE_URL}/pricing/price-lookup`, {
        target_volumes: targetVolumes,
        validity_days: validityDays,
        offer_type: lookupForm.offerType,
        config: pricingConfig,
      })

      setLookupResult(data)
    } catch (error) {
      setLookupError(getErrorMessage(error))
    } finally {
      setLookupLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 rounded-[2rem] border border-minteal-100 bg-white/90 p-6 shadow-sm lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.4em] text-minteal-400">AI Pricing engine</p>
          <h2 className="text-3xl font-semibold text-minteal-900">Dynamic pricing calculator</h2>
          <p className="max-w-3xl text-sm text-minteal-500">
            Run bundle calculations and reverse price lookup against pricing engine.
          </p>
          {configLoading ? (
            <p className="text-sm font-medium text-minteal-600">Loading default config from `/pricing/config`...</p>
          ) : null}
          {!configLoading && configError ? (
            <p className="text-sm font-medium text-amber-700">{configError}</p>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={resetAll}
            disabled={configLoading}
            className="inline-flex items-center gap-2 rounded-full border border-minteal-200 px-4 py-2 text-sm font-medium text-minteal-700 transition hover:border-minteal-400 hover:bg-white"
          >
            <ArrowPathIcon className="h-4 w-4" />
            Reset fields
          </button>
        </div>
      </header>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <form
          onSubmit={handleBundleSubmit}
          className="rounded-[2rem] border border-minteal-100 bg-white/90 p-6 shadow-sm"
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-minteal-400">Bundle</p>
              <h3 className="mt-2 text-2xl font-semibold text-minteal-900">Bundle calculator</h3>
              <p className="mt-2 text-sm text-minteal-500">
                Send service price allocations.
              </p>
            </div>
            <CalculatorIcon className="h-10 w-10 rounded-2xl bg-minteal-100 p-2 text-minteal-700" />
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium text-minteal-700">
              Voice price allocation
              <input
                type="number"
                min={pricingConfig.minimums.price.voice}
                value={bundleForm.voice}
                onChange={(event) => updateBundleField('voice', event.target.value)}
                placeholder="e.g. 150"
                className={fieldClassName}
              />
            </label>
            <label className="text-sm font-medium text-minteal-700">
              Data price allocation
              <input
                type="number"
                min={pricingConfig.minimums.price.data}
                value={bundleForm.data}
                onChange={(event) => updateBundleField('data', event.target.value)}
                placeholder="e.g. 300"
                className={fieldClassName}
              />
            </label>
            <label className="text-sm font-medium text-minteal-700">
              SMS price allocation
              <input
                type="number"
                min={0}
                value={bundleForm.sms}
                onChange={(event) => updateBundleField('sms', event.target.value)}
                placeholder="e.g. 50"
                className={fieldClassName}
              />
            </label>
            <label className="text-sm font-medium text-minteal-700">
              Custom validity
              <input
                type="number"
                min={1}
                value={bundleForm.customValidity}
                onChange={(event) => updateBundleField('customValidity', event.target.value)}
                placeholder="Overrides standard validity"
                className={fieldClassName}
              />
            </label>
            <label className="text-sm font-medium text-minteal-700">
              Standard validity
              <select
                value={bundleForm.standardValidity}
                onChange={(event) => updateBundleField('standardValidity', Number(event.target.value))}
                className={fieldClassName}
              >
                {VALIDITY_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {value} Day{value > 1 ? 's' : ''}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium text-minteal-700">
              Offer type
              <select
                value={bundleForm.offerType}
                onChange={(event) => updateBundleField('offerType', event.target.value as OfferType)}
                className={fieldClassName}
              >
                {OFFER_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-6 flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-minteal-400">Total allocation</p>
              <p className="text-2xl font-semibold text-minteal-900">Fr {bundleTotalPrice.toFixed(2)}</p>
            </div>
            <button
              type="submit"
              disabled={bundleLoading || configLoading}
              className="inline-flex items-center gap-2 rounded-full bg-minteal-900 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-minteal-900/20 transition hover:bg-minteal-800 disabled:cursor-not-allowed disabled:bg-minteal-400"
            >
              {bundleLoading ? 'Calculating...' : 'Calculate bundle'}
            </button>
          </div>

          <div className="mt-6">
            {bundleLoading ? <LoadingState message="Calculating bundle offer" /> : null}
            {!bundleLoading && bundleError ? <ErrorState message={bundleError} /> : null}
            {!bundleLoading && !bundleError && bundleResult ? (
              <section
                className={`${resultCardClassName} bg-gradient-to-br from-minteal-900 via-minteal-800 to-minteal-600`}
              >
                <p className="text-xs uppercase tracking-[0.3em] text-minteal-100/80">Bundle Result</p>
                <div className="mt-4 rounded-2xl bg-white/10 p-4">
                  <p className="text-sm text-minteal-50/80">Total Price</p>
                  <p className="mt-1 text-3xl font-semibold">Fr {bundleTotalPrice.toFixed(2)}</p>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  {Object.entries(bundleResult.units).map(([service, units]) => (
                    <article key={service} className="rounded-2xl bg-white/10 p-4">
                      <p className="text-sm text-minteal-50/75">{service}</p>
                      <p className="mt-2 text-xl font-semibold">{units}</p>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}
          </div>
        </form>

        <form
          onSubmit={handleLookupSubmit}
          className="rounded-[2rem] border border-minteal-100 bg-white/90 p-6 shadow-sm"
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-minteal-400">Lookup</p>
              <h3 className="mt-2 text-2xl font-semibold text-minteal-900">Price lookup</h3>
              <p className="mt-2 text-sm text-minteal-500">
                Reverse-calculate prices from target volumes.
              </p>
            </div>
            <CurrencyDollarIcon className="h-10 w-10 rounded-2xl bg-emerald-100 p-2 text-emerald-700" />
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium text-minteal-700">
              Target minutes
              <input
                type="number"
                min={pricingConfig.minimums.volume.voice}
                value={lookupForm.voice}
                onChange={(event) => updateLookupField('voice', event.target.value)}
                placeholder="e.g. 10"
                className={fieldClassName}
              />
            </label>
            <label className="text-sm font-medium text-minteal-700">
              Target MB
              <input
                type="number"
                min={pricingConfig.minimums.volume.data}
                value={lookupForm.data}
                onChange={(event) => updateLookupField('data', event.target.value)}
                placeholder="e.g. 500"
                className={fieldClassName}
              />
            </label>
            <label className="text-sm font-medium text-minteal-700">
              Target SMS
              <input
                type="number"
                min={0}
                value={lookupForm.sms}
                onChange={(event) => updateLookupField('sms', event.target.value)}
                placeholder="e.g. 20"
                className={fieldClassName}
              />
            </label>
            <label className="text-sm font-medium text-minteal-700">
              Custom validity
              <input
                type="number"
                min={1}
                value={lookupForm.customValidity}
                onChange={(event) => updateLookupField('customValidity', event.target.value)}
                placeholder="Overrides standard validity"
                className={fieldClassName}
              />
            </label>
            <label className="text-sm font-medium text-minteal-700">
              Standard validity
              <select
                value={lookupForm.standardValidity}
                onChange={(event) => updateLookupField('standardValidity', Number(event.target.value))}
                className={fieldClassName}
              >
                {VALIDITY_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {value} Day{value > 1 ? 's' : ''}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium text-minteal-700">
              Offer type
              <select
                value={lookupForm.offerType}
                onChange={(event) => updateLookupField('offerType', event.target.value as OfferType)}
                className={fieldClassName}
              >
                {OFFER_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-6 flex items-center justify-end">
            <button
              type="submit"
              disabled={lookupLoading || configLoading}
              className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-700/20 transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-emerald-300"
            >
              {lookupLoading ? 'Looking up...' : 'Lookup price'}
            </button>
          </div>

          <div className="mt-6">
            {lookupLoading ? <LoadingState message="Calculating price from target volume" /> : null}
            {!lookupLoading && lookupError ? <ErrorState message={lookupError} /> : null}
            {!lookupLoading && !lookupError && lookupResult ? (
              <section
                className={`${resultCardClassName} bg-gradient-to-br from-emerald-700 via-emerald-600 to-teal-500`}
              >
                <p className="text-xs uppercase tracking-[0.3em] text-emerald-50/80">Lookup Result</p>
                <div className="mt-4 rounded-2xl bg-white/10 p-4">
                  <p className="text-sm text-emerald-50/80">Calculated Price</p>
                  <p className="mt-1 text-3xl font-semibold">
                    Fr {lookupResult.calculated_price.toFixed(2)}
                  </p>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  {(['voice', 'data', 'sms'] as ServiceKey[]).map((service) => {
                    const value = lookupForm[service]
                    if (value.trim() === '' || Number(value) <= 0) {
                      return null
                    }

                    return (
                      <article key={service} className="rounded-2xl bg-white/10 p-4">
                        <p className="text-sm text-emerald-50/75">{SERVICE_LABELS[service]}</p>
                        <p className="mt-2 text-xl font-semibold">
                          {value} {pricingConfig.services[service].unit_name}
                        </p>
                      </article>
                    )
                  })}
                </div>
                {lookupResult.individual_prices && Object.keys(lookupResult.individual_prices).length > 0 ? (
                  <div className="mt-4 rounded-2xl bg-white/10 p-4">
                    <p className="text-sm text-emerald-50/80">Individual service prices</p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-3">
                      {Object.entries(lookupResult.individual_prices).map(([service, price]) => (
                        <div key={service} className="rounded-2xl bg-white/10 p-3">
                          <p className="text-xs uppercase tracking-[0.2em] text-emerald-50/70">{service}</p>
                          <p className="mt-1 font-semibold">Fr {price.toFixed(2)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </section>
            ) : null}
          </div>
        </form>
      </div>

      <section className="space-y-5 rounded-[2rem] border border-minteal-100 bg-white/90 p-6 shadow-sm">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-minteal-400">Visualization</p>
            <h3 className="mt-2 text-2xl font-semibold text-minteal-900">Pricing algorithm curves</h3>
          </div>
          <p className="text-sm font-medium text-minteal-500">
            {visualizationLoading ? 'Loading chart data from /pricing/visualization...' : 'API chart data'}
          </p>
        </div>

        {visualizationLoading ? <LoadingState message="Loading pricing visualization data" /> : null}
        {!visualizationLoading && visualizationError ? <ErrorState message={visualizationError} /> : null}

        {!visualizationLoading && !visualizationError ? (
          <div className="grid gap-6 xl:grid-cols-2">
            {pricingChartOptions.map(({ service, option }) => (
              <article
                key={service}
                className="overflow-hidden rounded-3xl border border-minteal-100 bg-gradient-to-br from-white via-white to-minteal-50/70 p-5 shadow-sm shadow-minteal-900/5"
              >
                <ReactECharts option={option} notMerge lazyUpdate style={{ height: 500, width: '100%' }} />
              </article>
            ))}
          </div>
        ) : null}
      </section>

      <section className="space-y-6 rounded-[2rem] border border-minteal-100 bg-white/90 p-6 shadow-sm">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-minteal-400">Configuration</p>
            <h3 className="mt-2 text-2xl font-semibold text-minteal-900">Pricing parameters</h3>
            <p className="mt-2 max-w-3xl text-sm text-minteal-500">
            </p>
          </div>
    
        </div>

        <div className="grid gap-6 xl:grid-cols-3">
          {(['voice', 'data', 'sms'] as ServiceKey[]).map((service) => (
            <section key={service} className="rounded-3xl border border-minteal-100 bg-minteal-50/60 p-5">
              <h4 className="text-lg font-semibold text-minteal-900">{SERVICE_LABELS[service]}</h4>
              <div className="mt-4 space-y-4">
                <label className="text-sm font-medium text-minteal-700">
                  Anchor Price
                  <input
                    type="number"
                    value={configForm.services[service].anchorPrice}
                    onChange={(event) =>
                      updateServiceConfigField(service, 'anchorPrice', Number(event.target.value))
                    }
                    className={fieldClassName}
                  />
                </label>
                <label className="text-sm font-medium text-minteal-700">
                  Anchor Rate
                  <input
                    type="number"
                    step="0.01"
                    value={configForm.services[service].anchorRate}
                    onChange={(event) =>
                      updateServiceConfigField(service, 'anchorRate', Number(event.target.value))
                    }
                    className={fieldClassName}
                  />
                </label>
                <label className="text-sm font-medium text-minteal-700">
                  Floor Rate
                  <input
                    type="number"
                    step="0.01"
                    value={configForm.services[service].floorRate}
                    onChange={(event) =>
                      updateServiceConfigField(service, 'floorRate', Number(event.target.value))
                    }
                    className={fieldClassName}
                  />
                </label>
                <div className="rounded-2xl border border-minteal-200 bg-white px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.2em] text-minteal-400">Decay (k)</p>
                  <p className="mt-1 text-sm font-semibold text-minteal-900">
                    {decayValues[service]?.toFixed(6) ?? 'N/A'}
                  </p>
                </div>
              </div>
            </section>
          ))}
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <section className="rounded-3xl border border-minteal-100 bg-minteal-50/60 p-5">
            <h4 className="text-lg font-semibold text-minteal-900">Validity premiums (%)</h4>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-medium text-minteal-700">
                2 Days
                <input
                  type="number"
                  value={configForm.validityPremiums.day2}
                  onChange={(event) => updateValidityField('day2', Number(event.target.value))}
                  className={fieldClassName}
                />
              </label>
              <label className="text-sm font-medium text-minteal-700">
                3 Days
                <input
                  type="number"
                  value={configForm.validityPremiums.day3}
                  onChange={(event) => updateValidityField('day3', Number(event.target.value))}
                  className={fieldClassName}
                />
              </label>
              <label className="text-sm font-medium text-minteal-700">
                7 Days
                <input
                  type="number"
                  value={configForm.validityPremiums.day7}
                  onChange={(event) => updateValidityField('day7', Number(event.target.value))}
                  className={fieldClassName}
                />
              </label>
              <label className="text-sm font-medium text-minteal-700">
                30 Days
                <input
                  type="number"
                  value={configForm.validityPremiums.day30}
                  onChange={(event) => updateValidityField('day30', Number(event.target.value))}
                  className={fieldClassName}
                />
              </label>
            </div>
          </section>

          <section className="rounded-3xl border border-minteal-100 bg-minteal-50/60 p-5">
            <h4 className="text-lg font-semibold text-minteal-900">Discount factors (%)</h4>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-medium text-minteal-700">
                Mixed bundle (2 services)
                <input
                  type="number"
                  value={configForm.discounts.mix2}
                  onChange={(event) => updateDiscountField('mix2', Number(event.target.value))}
                  className={fieldClassName}
                />
              </label>
              <label className="text-sm font-medium text-minteal-700">
                Mixed bundle (3 services)
                <input
                  type="number"
                  value={configForm.discounts.mix3}
                  onChange={(event) => updateDiscountField('mix3', Number(event.target.value))}
                  className={fieldClassName}
                />
              </label>
              <label className="text-sm font-medium text-minteal-700">
                BTL Normal
                <input
                  type="number"
                  value={configForm.discounts.btlNormal}
                  onChange={(event) => updateDiscountField('btlNormal', Number(event.target.value))}
                  className={fieldClassName}
                />
              </label>
              <label className="text-sm font-medium text-minteal-700">
                BTL Moderate
                <input
                  type="number"
                  value={configForm.discounts.btlModerate}
                  onChange={(event) => updateDiscountField('btlModerate', Number(event.target.value))}
                  className={fieldClassName}
                />
              </label>
              <label className="text-sm font-medium text-minteal-700 sm:col-span-2">
                BTL Aggressive
                <input
                  type="number"
                  value={configForm.discounts.btlAggressive}
                  onChange={(event) => updateDiscountField('btlAggressive', Number(event.target.value))}
                  className={fieldClassName}
                />
              </label>
            </div>
          </section>
        </div>

        <section className="rounded-3xl border border-minteal-100 bg-minteal-50/60 p-5">
          <h4 className="text-lg font-semibold text-minteal-900">Promotion mode parameters</h4>
          <p className="mt-2 text-sm text-minteal-500">
          </p>

          <div className="mt-6 grid gap-6 xl:grid-cols-3">
            {(['voice', 'data', 'sms'] as ServiceKey[]).map((service) => (
              <section key={service} className="rounded-3xl border border-minteal-100 bg-white p-5">
                <h5 className="text-lg font-semibold text-minteal-900">{SERVICE_LABELS[service]}</h5>
                <div className="mt-4 space-y-4">
                  <label className="text-sm font-medium text-minteal-700">
                    Starting Price
                    <input
                      type="number"
                      value={configForm.promotion[service].starting_price}
                      onChange={(event) =>
                        updatePromotionField(service, 'starting_price', Number(event.target.value))
                      }
                      className={fieldClassName}
                    />
                  </label>
                  <label className="text-sm font-medium text-minteal-700">
                    Ending Price
                    <input
                      type="number"
                      value={configForm.promotion[service].ending_price}
                      onChange={(event) =>
                        updatePromotionField(service, 'ending_price', Number(event.target.value))
                      }
                      className={fieldClassName}
                    />
                  </label>
                  <label className="text-sm font-medium text-minteal-700">
                    Discount (%)
                    <input
                      type="number"
                      value={configForm.promotion[service].discount}
                      onChange={(event) =>
                        updatePromotionField(service, 'discount', Number(event.target.value))
                      }
                      className={fieldClassName}
                    />
                  </label>
                  <label className="text-sm font-medium text-minteal-700">
                    Validity
                    <select
                      value={configForm.promotion[service].validity}
                      onChange={(event) =>
                        updatePromotionField(service, 'validity', Number(event.target.value))
                      }
                      className={fieldClassName}
                    >
                      <option value={-1}>-1 (Any)</option>
                      {VALIDITY_OPTIONS.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </section>
            ))}
          </div>
        </section>
      </section>
    </div>
  )
}

export default PricingEnginePage
