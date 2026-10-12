import { useState } from 'react'
import { Database, Eye, EyeOff, ShieldCheck, X, ArrowRight, LoaderCircle, CircleCheck } from 'lucide-react'
import Brand from './Brand.jsx'

export default function ConnectionModal({ open, initialValue, onClose, onConnect, connecting, error, connected }) {
  const [value, setValue] = useState(initialValue || '')
  const [show, setShow] = useState(false)

  if (!open) return null

  async function submit(event) {
    event.preventDefault()
    await onConnect(value.trim())
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="connection-modal" role="dialog" aria-modal="true" aria-labelledby="connect-title">
        <div className="modal-topline">
          <Brand />
          {connected && <button className="icon-button" onClick={onClose} aria-label="Close connection settings"><X size={18} /></button>}
        </div>
        <div className="modal-illustration"><div className="orbit orbit--one" /><div className="orbit orbit--two" /><span><Database size={31} /></span></div>
        <div className="modal-copy">
          <div className="eyebrow"><span className="eyebrow-dot" /> DATABASE CONNECTION</div>
          <h1 id="connect-title">{connected ? 'Connection settings' : 'Connect your database'}</h1>
          <p>Connect QueryMind to PostgreSQL to explore your schema and ask questions in plain English.</p>
        </div>
        <form onSubmit={submit} className="connection-form">
          <label htmlFor="connection-string">PostgreSQL connection string</label>
          <div className="connection-input-wrap">
            <Database size={17} />
            <input id="connection-string" autoFocus type={show ? 'text' : 'password'} value={value} onChange={(event) => setValue(event.target.value)} placeholder="postgresql://user:password@host:5432/database" required autoComplete="off" />
            <button type="button" className="input-action" onClick={() => setShow(!show)} aria-label={show ? 'Hide connection string' : 'Show connection string'}>{show ? <EyeOff size={17} /> : <Eye size={17} />}</button>
          </div>
          <div className="secure-note"><ShieldCheck size={15} /><span>Used by this browser session to connect directly to your API.</span></div>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button className="primary-button connect-submit" type="submit" disabled={connecting || !value.trim()}>
            {connecting ? <><LoaderCircle className="spin" size={17} /> Connecting…</> : connected ? <>Reconnect database <ArrowRight size={17} /></> : <>Connect database <ArrowRight size={17} /></>}
          </button>
          {connected && <div className="connected-note"><CircleCheck size={15} /> Currently connected to a database</div>}
        </form>
        <p className="modal-footnote">QueryMind only runs read-only queries through the configured backend.</p>
      </section>
    </div>
  )
}
