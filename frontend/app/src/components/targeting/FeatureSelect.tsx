import type { FeatureOption } from '../../api/graphsage'

type FeatureSelectProps = {
  id: string
  label: string
  value: string
  option?: FeatureOption
  disabled?: boolean
  required?: boolean
  onChange: (value: string) => void
}

const fieldClassName =
  'mt-2 w-full rounded-xl border border-minteal-200 bg-white px-3 py-2 text-sm font-medium text-minteal-900 outline-none transition focus:border-minteal-500 focus:ring-2 focus:ring-minteal-200 disabled:cursor-not-allowed disabled:bg-minteal-50'

const formatFeatureLabel = (value: string) =>
  value
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase())

const FeatureSelect = ({ id, label, value, option, disabled = false, required = false, onChange }: FeatureSelectProps) => {
  const values = option?.values ?? []

  return (
    <label htmlFor={id} className="block text-sm font-medium text-minteal-700">
      <span className="flex items-center justify-between gap-3">
        <span>{label}</span>
        {option ? (
          <span className="text-xs font-normal text-minteal-400">
            {option.total_values.toLocaleString()} value{option.total_values === 1 ? '' : 's'}
            {option.truncated ? ' shown partially' : ''}
          </span>
        ) : null}
      </span>
      <select
        id={id}
        value={value}
        disabled={disabled || values.length === 0}
        required={required}
        onChange={(event) => onChange(event.target.value)}
        className={fieldClassName}
      >
        <option value="">Select {label.toLowerCase()}</option>
        {values.map((item) => (
          <option key={item} value={item}>
            {formatFeatureLabel(item)}
          </option>
        ))}
      </select>
    </label>
  )
}

export default FeatureSelect
