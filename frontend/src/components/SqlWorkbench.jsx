import { useMemo, useState } from 'react'
import { Code2, Table2, Copy, Check, ChevronDown, ChevronUp, TerminalSquare, Rows3, Clock3, CircleCheck, ShieldAlert, Maximize2 } from 'lucide-react'
import { formatSql, statusLabel } from '../utils/format.js'

export default function SqlWorkbench({ activeMessage }) {
  const [tab, setTab] = useState('results')
  const [expanded, setExpanded] = useState(true)
  const [copied, setCopied] = useState(false)
  const response = activeMessage?.response
  const execution = response?.execution
  const validation = response?.sql_validation
  const sql = response?.sql || validation?.normalized_sql || ''
  const result = execution || null
  const columns = result?.columns || []
  const rows = result?.rows || []

  async function copySql() {
    await navigator.clipboard?.writeText(sql)
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }

  const elapsed = useMemo(() => response ? 'Complete' : 'Ready', [response])

  return (
    <section className={`sql-workbench ${expanded ? '' : 'sql-workbench--collapsed'}`}>
      <div className="workbench-titlebar"><div className="workbench-heading"><span className="workbench-icon"><TerminalSquare size={16} /></span><div><h3>Query workspace</h3><p>SQL editor &amp; result output</p></div></div><div className="workbench-tools"><span className={`execution-indicator ${response?.status === 'executed' ? 'is-success' : ''}`}><i />{elapsed}</span><button className="icon-button" title="Collapse panel" onClick={() => setExpanded(!expanded)}>{expanded ? <ChevronDown size={17} /> : <ChevronUp size={17} />}</button></div></div>
      {expanded && <>
        <div className="sql-editor-head"><div className="sql-editor-label"><Code2 size={15} /><span>SQL</span><span className="sql-language-badge">PostgreSQL</span></div><div className="sql-editor-actions"><button onClick={copySql} disabled={!sql}><span>{copied ? <Check size={13} /> : <Copy size={13} />}</span>{copied ? 'Copied' : 'Copy query'}</button></div></div>
        <div className="sql-code-area">
          {sql ? <pre className="sql-code"><code>{formatSql(sql).split('\n').map((line, index) => <span className="sql-line" key={index}><i>{String(index + 1).padStart(2, '0')}</i><span>{line.split(/(\bSELECT\b|\bFROM\b|\bWHERE\b|\bORDER BY\b|\bGROUP BY\b|\bLIMIT\b|\bCOUNT\b|\bAS\b|\bAND\b|\bOR\b)/gi).map((part, partIndex) => /^(SELECT|FROM|WHERE|ORDER BY|GROUP BY|LIMIT|COUNT|AS|AND|OR)$/i.test(part) ? <b key={partIndex}>{part}</b> : <span key={partIndex}>{part}</span>)}</span></span>)}</code></pre> : <div className="sql-placeholder"><Code2 size={19} /><span>Your generated SQL will appear here after your first question.</span></div>}
        </div>
        <div className="result-toolbar"><div className="result-tabs"><button className={tab === 'results' ? 'active' : ''} onClick={() => setTab('results')}><Table2 size={14} /> Results</button><button className={tab === 'messages' ? 'active' : ''} onClick={() => setTab('messages')}><TerminalSquare size={14} /> Messages</button></div><div className="result-meta">{response && <><span><Rows3 size={13} /> {result?.row_count ?? 0} rows</span><span><Clock3 size={13} /> {statusLabel(response.status)}</span></>}</div></div>
        <div className="result-content">
          {tab === 'results' ? result ? rows.length ? <div className="result-table-wrap"><table className="data-table result-data-table"><thead><tr><th className="row-number-head">#</th>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}><td className="row-number">{index + 1}</td>{columns.map((column) => <td key={column}>{row[column] == null ? <span className="null-value">NULL</span> : String(row[column])}</td>)}</tr>)}</tbody></table></div> : <div className="result-empty"><Table2 size={20} /><strong>Query completed — no rows returned</strong><span>The database returned an empty result set.</span></div> : sql ? <div className="result-empty"><ShieldAlert size={20} /><strong>Query has not been executed</strong><span>{response?.message || 'No execution results are available for this response.'}</span></div> : <div className="result-empty result-empty--quiet"><Rows3 size={20} /><strong>Results will appear here</strong><span>Ask a question above to populate this workspace.</span></div> : <div className="message-output">{response ? <><div className="message-output-status"><CircleCheck size={15} /> {response.message || statusLabel(response.status)}</div>{(response.sql_validation?.issues || []).map((issue, index) => <p className="validation-issue" key={index}>{issue}</p>)}{response.execution?.truncated && <p>Results are limited to the maximum row count.</p>}</> : <span>Messages and validation details will appear here.</span>}</div>}
        </div>
        <div className="workbench-statusbar"><span><span className="status-dot" /> PostgreSQL</span><span>Read-only execution</span><span>{result?.truncated ? 'Results truncated' : result ? `${result.row_count} rows returned` : 'No active result'}</span></div>
      </>}
    </section>
  )
}
