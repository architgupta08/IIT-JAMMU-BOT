import React, { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import styles from './ChatWindow.module.css'

const LANG_FLAGS = {
  en: '🇬🇧', hi: '🇮🇳', ur: '🇵🇰', pa: '🇮🇳',
  ta: '🇮🇳', te: '🇮🇳', bn: '🇧🇩', mr: '🇮🇳',
  gu: '🇮🇳', kn: '🇮🇳', ml: '🇮🇳', ar: '🇸🇦',
  zh: '🇨🇳', fr: '🇫🇷', de: '🇩🇪', es: '🇪🇸',
}

function TypingIndicator() {
  return (
    <div className={styles.typing}>
      <span /><span /><span />
    </div>
  )
}

function Message({ msg }) {
  const isBot = msg.role === 'bot'
  const flag = msg.detectedLang ? (LANG_FLAGS[msg.detectedLang] || '🌐') : null
  const timeStr = msg.timestamp
    ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : ''

  return (
    <div className={`${styles.msgRow} ${isBot ? styles.botRow : styles.userRow}`}>
      {isBot && (
        <div className={styles.avatar} title="IIT Jammu AI">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M12 2C6.48 2 2 5.92 2 10.7c0 2.7 1.38 5.1 3.56 6.75L4 21l4.5-2.05C9.6 19.3 10.77 19.5 12 19.5c5.52 0 10-3.92 10-8.8C22 5.92 17.52 2 12 2z"
              fill="#003366"/>
            <circle cx="8.5" cy="10.5" r="1.2" fill="white"/>
            <circle cx="12" cy="10.5" r="1.2" fill="white"/>
            <circle cx="15.5" cy="10.5" r="1.2" fill="white"/>
          </svg>
        </div>
      )}

      <div className={styles.msgContent}>
        <div className={`${styles.bubble} ${isBot ? styles.botBubble : styles.userBubble} ${msg.isError ? styles.errorBubble : ''}`}>
          {isBot ? (
            <div className={styles.markdown}>
              <ReactMarkdown>{msg.text}</ReactMarkdown>
            </div>
          ) : (
            <span>{msg.text}</span>
          )}
        </div>

        <div className={styles.meta}>
          <span className={styles.time}>{timeStr}</span>
          {flag && <span className={styles.lang}>{flag}</span>}
          {msg.confidence !== undefined && msg.confidence > 0 && (
            <span className={styles.confidence}
              title={`Confidence: ${Math.round(msg.confidence * 100)}%`}>
              {msg.confidence > 0.7 ? '✓' : '~'}
            </span>
          )}
        </div>

        {/* Source citations */}
        {isBot && msg.sources && msg.sources.length > 0 && (
          <div className={styles.sources}>
            <span className={styles.sourcesLabel}>Sources:</span>
            {msg.sources.map((s, i) => (
              <span key={i} className={styles.sourceTag} title={s.path}>
                📄 {s.title}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function ChatWindow({ messages, loading, suggestions, onSend, onClose, onClear }) {
  const [input, setInput] = useState('')
  const [showSugg, setShowSugg] = useState(true)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 100)
  }, [])

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed) return
    setInput('')
    setShowSugg(false)
    onSend(trimmed)
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSuggestion = (q) => {
    setShowSugg(false)
    onSend(q)
  }

  return (
    <div className={styles.window}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.headerAvatar}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path d="M12 2C6.48 2 2 5.92 2 10.7c0 2.7 1.38 5.1 3.56 6.75L4 21l4.5-2.05C9.6 19.3 10.77 19.5 12 19.5c5.52 0 10-3.92 10-8.8C22 5.92 17.52 2 12 2z"
                fill="white"/>
              <circle cx="8.5" cy="10.5" r="1.1" fill="#003366"/>
              <circle cx="12" cy="10.5" r="1.1" fill="#003366"/>
              <circle cx="15.5" cy="10.5" r="1.1" fill="#003366"/>
            </svg>
          </div>
          <div>
            <div className={styles.headerTitle}>IIT Jammu Assistant</div>
            <div className={styles.headerStatus}>
              <span className={styles.dot} /> Powered by Gemini AI
            </div>
          </div>
        </div>
        <div className={styles.headerActions}>
          <button onClick={onClear} title="Clear chat" className={styles.iconBtn}>
            🗑️
          </button>
          <button onClick={onClose} title="Close" className={styles.iconBtn}>
            ✕
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className={styles.messages}>
        {messages.map(msg => (
          <Message key={msg.id} msg={msg} />
        ))}

        {loading && (
          <div className={`${styles.msgRow} ${styles.botRow}`}>
            <div className={styles.avatar}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path d="M12 2C6.48 2 2 5.92 2 10.7c0 2.7 1.38 5.1 3.56 6.75L4 21l4.5-2.05C9.6 19.3 10.77 19.5 12 19.5c5.52 0 10-3.92 10-8.8C22 5.92 17.52 2 12 2z"
                  fill="#003366"/>
              </svg>
            </div>
            <div className={styles.msgContent}>
              <div className={`${styles.bubble} ${styles.botBubble}`}>
                <TypingIndicator />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested questions */}
      {showSugg && messages.length <= 1 && suggestions.length > 0 && (
        <div className={styles.suggestions}>
          <p className={styles.suggLabel}>💡 Try asking:</p>
          <div className={styles.suggGrid}>
            {suggestions.map((q, i) => (
              <button key={i} className={styles.suggBtn} onClick={() => handleSuggestion(q)}>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div className={styles.inputArea}>
        <textarea
          ref={inputRef}
          className={styles.input}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask about IIT Jammu... (any language)"
          rows={1}
          maxLength={2000}
          disabled={loading}
        />
        <button
          className={`${styles.sendBtn} ${loading || !input.trim() ? styles.sendDisabled : ''}`}
          onClick={handleSend}
          disabled={loading || !input.trim()}
          title="Send message"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>

      <div className={styles.disclaimer}>
        AI responses may not always be 100% accurate. Verify important information at{' '}
        <a href="https://www.iitjammu.ac.in" target="_blank" rel="noreferrer">iitjammu.ac.in</a>
      </div>
    </div>
  )
}
