import { useState } from 'react'
import { ChevronDown, ChevronRight, Search, Table2, KeyRound, Link2, PanelLeftClose, PanelLeftOpen, Database, RefreshCw, Settings2, CircleDot } from 'lucide-react'
import Brand from './Brand.jsx'
import { getTableColumns } from '../utils/format.js'

function TableItem({ table, selected, onSelect }) {
  const [expanded, setExpanded] = useState(false)
  const columns = getTableColumns(table)
  const name = table.table || table.name || 'table'
  return (
    <div className="schema-table">
      <button className={`schema-table-button ${selected === name ? 'is-selected' : ''}`} onClick={() => { setExpanded(!expanded); onSelect(name) }}>
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <Table2 size={15} className="table-glyph" />
        <span>{name}</span>
        <span className="column-count">{columns.length}</span>
      </button>
      {expanded && <div className="column-list">
        {columns.length ? columns.map((column) => {
          const item = table.columns.find((entry) => (typeof entry === 'string' ? entry : entry.name) === column)
          const primary = typeof item === 'object' && item.primary_key
          return <div className="column-item" key={column}>{primary ? <KeyRound size={12} /> : <CircleDot size={11} />}<span>{column}</span></div>
        }) : <div className="column-empty">Column metadata unavailable</div>}
        {(table.foreign_keys || []).length > 0 && <div className="relation-hint"><Link2 size={12} /> {table.foreign_keys.length} relationships</div>}
      </div>}
    </div>
  )
}

export default function Sidebar({ schema, databaseName, onOpenConnection, onRefreshSchema, refreshing, mobileOpen, onCloseMobile }) {
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState('')
  const tables = (schema?.tables || []).filter((table) => (table.table || table.name || '').toLowerCase().includes(filter.toLowerCase()))
  return (
    <>
      {mobileOpen && <button className="mobile-scrim" aria-label="Close sidebar" onClick={onCloseMobile} />}
      <aside className={`sidebar ${mobileOpen ? 'sidebar--mobile-open' : ''}`}>
        <div className="sidebar-brand-row"><Brand /><button className="sidebar-close icon-button" onClick={onCloseMobile} aria-label="Close sidebar"><PanelLeftClose size={17} /></button></div>
        <div className="workspace-label">WORKSPACE</div>
        <button className="database-card" onClick={onOpenConnection}>
          <span className="database-card-icon"><Database size={17} /></span>
          <span className="database-card-copy"><strong>{databaseName || 'PostgreSQL'}</strong><small><i /> Connected database</small></span>
          <Settings2 size={15} className="database-settings" />
        </button>
        <div className="schema-heading">
          <div><span className="schema-heading-title">Database schema</span><span className="schema-count">{schema?.table_count ?? schema?.tables?.length ?? 0} tables</span></div>
          <button className={`icon-button refresh-button ${refreshing ? 'is-spinning' : ''}`} onClick={onRefreshSchema} disabled={refreshing} title="Refresh schema"><RefreshCw size={15} /></button>
        </div>
        <div className="schema-search"><Search size={15} /><input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Find a table..." aria-label="Find a table" /></div>
        <div className="schema-tree">
          {tables.map((table) => <TableItem key={`${table.schema || 'public'}.${table.table || table.name}`} table={table} selected={selected} onSelect={setSelected} />)}
          {tables.length === 0 && <div className="empty-filter">{schema?.tables?.length ? 'No matching tables' : 'Connect a database to browse tables.'}</div>}
        </div>
        <div className="sidebar-bottom"><div className="api-status"><span className="status-pulse" /> API connected</div><div className="sidebar-version">QUERYMIND <span>•</span> PREVIEW</div></div>
      </aside>
    </>
  )
}
