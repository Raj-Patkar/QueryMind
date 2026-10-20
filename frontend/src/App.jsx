import { useCallback, useEffect, useMemo, useState } from 'react'
import { Menu, PlugZap, CircleHelp, PanelLeft, ChevronDown, Database, Wifi, AlertCircle } from 'lucide-react'
import Brand from './components/Brand.jsx'
import Sidebar from './components/Sidebar.jsx'
import ConnectionModal from './components/ConnectionModal.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import SqlWorkbench from './components/SqlWorkbench.jsx'
import { askQuery, testDatabase } from './services/api.js'
import './styles/app.css'

const STORAGE_KEY = 'querymind.connectionString'

function databaseLabel(connectionString) {
  try {
    const parsed = new URL(connectionString)
    const name = parsed.pathname.replace(/^\/+/, '')
    return name || 'PostgreSQL'
  } catch {
    return 'PostgreSQL'
  }
}

export default function App() {
  const [connectionString, setConnectionString] = useState(() => sessionStorage.getItem(STORAGE_KEY) || '')
  const [schema, setSchema] = useState(null)
  const [connected, setConnected] = useState(false)
  const [modalOpen, setModalOpen] = useState(true)
  const [connecting, setConnecting] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [connectionError, setConnectionError] = useState('')
  const [messages, setMessages] = useState([])
  const [asking, setAsking] = useState(false)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const [notice, setNotice] = useState('')

  const databaseName = useMemo(() => databaseLabel(connectionString), [connectionString])
  const activeMessage = [...messages].reverse().find((message) => message.role === 'assistant' && message.response)

  const connect = useCallback(async (value) => {
    if (!value) return
    setConnecting(true)
    setConnectionError('')
    try {
      const result = await testDatabase(value)
      setConnectionString(value)
      sessionStorage.setItem(STORAGE_KEY, value)
      setSchema(result)
      setConnected(true)
      setModalOpen(false)
      setMessages([])
      setNotice(`Connected to ${databaseLabel(value)}`)
    } catch (error) {
      setConnectionError(error.message || 'Unable to connect to the database.')
      setConnected(false)
    } finally {
      setConnecting(false)
    }
  }, [])

  const refreshSchema = useCallback(async () => {
    if (!connectionString) return
    setRefreshing(true)
    try {
      const result = await testDatabase(connectionString)
      setSchema(result)
      setNotice('Database schema refreshed')
    } catch (error) {
      setNotice(error.message || 'Unable to refresh schema')
    } finally {
      setRefreshing(false)
    }
  }, [connectionString])

  useEffect(() => {
    if (!connectionString) return
    let cancelled = false
    testDatabase(connectionString).then((result) => {
      if (cancelled) return
      setSchema(result)
      setConnected(true)
      setModalOpen(false)
    }).catch(() => {
      if (cancelled) return
      setConnected(false)
      setModalOpen(true)
      setConnectionError('The saved connection could not be verified. Check the backend and reconnect.')
    })
    return () => { cancelled = true }
  }, []) // Restore the saved session once on startup.

  useEffect(() => {
    if (!notice) return
    const id = window.setTimeout(() => setNotice(''), 3200)
    return () => window.clearTimeout(id)
  }, [notice])

  async function handleAsk(question) {
    const userMessage = { id: crypto.randomUUID(), role: 'user', content: question, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
    setMessages((current) => [...current, userMessage])
    setAsking(true)
    try {
      const response = await askQuery({ question, connectionString, conversationHistory: messages.slice(-8) })
      const execution = response.execution
      const content = response.status === 'executed'
        ? `I ran your query successfully and found ${execution?.row_count ?? 0} row${execution?.row_count === 1 ? '' : 's'}. The SQL and complete result set are available in the query workspace below.`
          + (response.rewritten_question ? ` I understood your question as: "${response.rewritten_question}".` : '')
          + (response.fallback_used ? ' The top-ranked SQL returned no rows, so this is the next-best candidate; please check the SQL.' : '')
        : response.message || 'I could not complete this request.'
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', content, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), response, result: response.execution || null, sql: response.sql }])
    } catch (error) {
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', content: 'I could not complete that request.', error: error.message, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }])
    } finally {
      setAsking(false)
    }
  }

  function clearConversation() {
    setMessages([])
  }

  function runSuggestion(question) {
    handleAsk(question)
  }

  return (
    <div className="app-shell">
      <Sidebar schema={schema} databaseName={databaseName} onOpenConnection={() => { setConnectionError(''); setModalOpen(true) }} onRefreshSchema={refreshSchema} refreshing={refreshing} mobileOpen={mobileSidebarOpen} onCloseMobile={() => setMobileSidebarOpen(false)} />
      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left"><button className="mobile-menu icon-button" onClick={() => setMobileSidebarOpen(true)} aria-label="Open navigation"><Menu size={19} /></button><div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>Query assistant</strong></div></div>
          <div className="topbar-right"><div className={`connection-status ${connected ? 'is-connected' : ''}`}><span />{connected ? 'Database connected' : 'Not connected'}</div><button className="topbar-connect" onClick={() => { setConnectionError(''); setModalOpen(true) }}><PlugZap size={15} /> <span>{connected ? 'Connection' : 'Connect database'}</span><ChevronDown size={14} /></button></div>
        </header>
        <div className="workspace-content">
          <div className="page-heading"><div><div className="page-eyebrow"><span className="page-eyebrow-line" /> DATABASE INTELLIGENCE</div><h1>Good data starts<br className="mobile-break" /> with a question<span>.</span></h1><p>Ask in plain English. Query your database with confidence.</p></div><div className="page-heading-badge"><div className="badge-icon"><Database size={18} /></div><div><span>ACTIVE DATABASE</span><strong>{connected ? databaseName : 'Awaiting connection'}</strong></div></div></div>
          {notice && <div className="toast-notice"><Wifi size={14} />{notice}</div>}
          {!connected && <div className="connection-callout"><div className="callout-icon"><AlertCircle size={18} /></div><div><strong>Connect a PostgreSQL database to begin</strong><p>Your schema, chat, and query results will appear here.</p></div><button className="primary-button" onClick={() => setModalOpen(true)}>Connect database</button></div>}
          <div className="workspace-grid">
            <ChatPanel connected={connected} messages={messages} onAsk={handleAsk} asking={asking} onSuggestion={runSuggestion} onClear={clearConversation} />
            <SqlWorkbench activeMessage={activeMessage} />
          </div>
          <footer className="app-footer"><span><Brand compact /> <span>QueryMind</span> <span className="footer-divider">·</span> Natural language, structured answers.</span><span><CircleHelp size={13} /> AI-generated SQL should always be reviewed.</span></footer>
        </div>
      </main>
      <ConnectionModal open={modalOpen} initialValue={connectionString} onClose={() => setModalOpen(false)} onConnect={connect} connecting={connecting} error={connectionError} connected={connected} />
    </div>
  )
}
