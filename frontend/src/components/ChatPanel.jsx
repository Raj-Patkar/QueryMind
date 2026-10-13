import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Sparkles, UserRound, Bot, Copy, Check, LoaderCircle, RotateCcw, ChevronDown, ChevronUp, Database, AlertCircle } from 'lucide-react'
import { statusLabel } from '../utils/format.js'

const suggestions = [
  { title: 'Explore customers', question: 'List all customer names', icon: 'people' },
  { title: 'Product overview', question: 'List all product names', icon: 'box' },
  { title: 'Count records', question: 'How many customers are there?', icon: 'count' },
]

function Message({ message }) {
  const [copied, setCopied] = useState(false)
  async function copyText() {
    await navigator.clipboard?.writeText(message.sql || message.content || '')
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }
  return (
    <article className={`chat-message ${message.role === 'user' ? 'chat-message--user' : 'chat-message--assistant'}`}>
      <div className={`message-avatar ${message.role === 'user' ? 'message-avatar--user' : ''}`}>{message.role === 'user' ? <UserRound size={16} /> : <Bot size={17} />}</div>
      <div className="message-body">
        <div className="message-author">{message.role === 'user' ? 'You' : 'QueryMind'} <span>{message.time}</span></div>
        <div className="message-bubble">
          <p>{message.content}</p>
          {message.result && <div className="inline-result">
            <div className="inline-result-head"><span><Database size={14} /> Query results</span><span className="row-pill">{message.result.row_count ?? message.result.rows?.length ?? 0} rows</span></div>
            {message.result.rows?.length ? <div className="inline-table-wrap"><table className="data-table"><thead><tr>{message.result.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{message.result.rows.slice(0, 5).map((row, i) => <tr key={i}>{message.result.columns.map((column) => <td key={column}>{row[column] == null ? <span className="null-value">NULL</span> : String(row[column])}</td>)}</tr>)}</tbody></table>{message.result.rows.length > 5 && <div className="inline-table-more">+ {message.result.rows.length - 5} more rows below</div>}</div> : <div className="no-rows">No rows returned.</div>}
          </div>}
          {message.error && <div className="message-error"><AlertCircle size={15} />{message.error}</div>}
          {message.response && <div className={`response-status response-status--${message.response.status === 'executed' ? 'success' : 'warning'}`}><span className="response-status-dot" />{statusLabel(message.response.status)}</div>}
        </div>
        {message.role === 'assistant' && <div className="message-actions"><button onClick={copyText} title="Copy response"><span>{copied ? <Check size={13} /> : <Copy size={13} />}</span>{copied ? 'Copied' : message.sql ? 'Copy SQL' : 'Copy response'}</button></div>}
      </div>
    </article>
  )
}

export default function ChatPanel({ connected, messages, onAsk, asking, onSuggestion, onClear, onShowSql }) {
  const [question, setQuestion] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(true)
  const textareaRef = useRef(null)
  const bottomRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, asking])

  async function submit(event) {
    event.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || asking || !connected) return
    setQuestion('')
    setShowSuggestions(false)
    await onAsk(trimmed)
    textareaRef.current?.focus()
  }

  function onKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit(event)
    }
  }

  return (
    <section className="chat-panel">
      <div className="chat-topbar"><div><div className="panel-kicker"><Sparkles size={13} /> NATURAL LANGUAGE</div><h2>Ask your data</h2><p>Ask a question. Get answers from your database.</p></div><div className="chat-top-actions"><span className="model-chip"><span /> AI assistant</span><button className="icon-button" onClick={onClear} title="Clear conversation"><RotateCcw size={16} /></button></div></div>
      <div className="conversation-scroll">
        {messages.length === 0 ? <div className="welcome-state">
          <div className="welcome-orb"><Sparkles size={23} /></div>
          <div className="welcome-eyebrow">YOUR DATA, IN PLAIN ENGLISH</div>
          <h3>What would you like<br />to know today?</h3>
          <p>Explore your connected database without writing SQL by hand.</p>
          {showSuggestions && <div className="suggestion-grid">{suggestions.map((item, index) => <button className="suggestion-card" key={item.title} onClick={() => onSuggestion(item.question)}><span className={`suggestion-icon suggestion-icon--${index}`}><Database size={16} /></span><span><strong>{item.title}</strong><small>{item.question}</small></span><ArrowUp size={15} className="suggestion-arrow" /></button>)}</div>}
        </div> : <div className="messages-list">{messages.map((message) => <Message key={message.id} message={message} />)}{asking && <article className="chat-message chat-message--assistant"><div className="message-avatar"><Bot size={17} /></div><div className="message-body"><div className="message-author">QueryMind <span>thinking</span></div><div className="typing-bubble"><span /><span /><span /></div></div></article>}<div ref={bottomRef} /></div>}
      </div>
      <div className="composer-wrap">
        <form className="composer" onSubmit={submit}><textarea ref={textareaRef} value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={onKeyDown} placeholder={connected ? 'Ask anything about your database…' : 'Connect a database to get started'} rows={2} disabled={!connected || asking} aria-label="Ask a question" /><div className="composer-footer"><span><kbd>Enter</kbd> to send <span className="composer-separator">·</span> <kbd>Shift + Enter</kbd> for new line</span><button type="submit" className="send-button" disabled={!question.trim() || asking || !connected} aria-label="Send question">{asking ? <LoaderCircle className="spin" size={17} /> : <ArrowUp size={18} />}</button></div></form>
        <div className="composer-disclaimer">QueryMind can make mistakes. Review SQL and results before relying on them.</div>
      </div>
    </section>
  )
}
