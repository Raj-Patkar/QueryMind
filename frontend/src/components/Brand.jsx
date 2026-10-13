import { DatabaseZap } from 'lucide-react'

export default function Brand({ compact = false }) {
  return (
    <div className={`brand ${compact ? 'brand--compact' : ''}`}>
      <span className="brand-mark"><DatabaseZap size={19} strokeWidth={2.2} /></span>
      {!compact && <span className="brand-name">Query<span>Mind</span></span>}
    </div>
  )
}
