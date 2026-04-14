import React, { useState, useEffect, useRef } from 'react'
import ChatWindow from './ChatWindow.jsx'
import styles from './ChatBot.module.css'

const WELCOME_MSG = {
  id: 'welcome',
  role: 'bot',
  text: `**Namaste! 🙏 Welcome to IIT Jammu AI Assistant**

I can help you with:
- 🎓 B.Tech, M.Tech & Ph.D programs
- 💰 Fee structure & scholarships
- 📋 Admission process & eligibility
- 👨‍🏫 Faculty information
- 🏠 Hostel & campus facilities
- 📊 Placement statistics

**Ask me anything in any language — Hindi, English, Urdu, or your preferred language!**

*आप हिंदी में भी पूछ सकते हैं!*`,
  timestamp: new Date(),
  sources: [],
}

export default function ChatBot() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([WELCOME_MSG])
  const [loading, setLoading] = useState(false)
  const [sessionId] = useState(() => `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`)
  const [unread, setUnread] = useState(0)
  const [suggestions, setSuggestions] = useState([])

  // Load suggestions on mount
  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/suggestions`)
      .then(r => r.json())
      .then(d => setSuggestions(d.questions?.slice(0, 4) || []))
      .catch(() => setSuggestions([
        'What B.Tech programs are offered?',
        'What is the fee structure?',
        'How to apply for admissions?',
        'Tell me about hostel facilities',
      ]))
  }, [])

  useEffect(() => {
    if (!open && messages.length > 1) setUnread(v => v + 1)
  }, [messages])

  const handleOpen = () => { setOpen(true); setUnread(0) }
  const handleClose = () => setOpen(false)

  const sendMessage = async (text) => {
    if (!text.trim() || loading) return

    const userMsg = {
      id: `u_${Date.now()}`,
      role: 'user',
      text: text.trim(),
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
      const res = await fetch(`${apiBase}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text.trim(), session_id: sessionId }),
      })

      if (!res.ok) throw new Error(`Server error: ${res.status}`)
      const data = await res.json()

      const botMsg = {
        id: `b_${Date.now()}`,
        role: 'bot',
        text: data.answer,
        timestamp: new Date(),
        sources: data.sources || [],
        confidence: data.confidence,
        detectedLang: data.detected_language,
      }
      setMessages(prev => [...prev, botMsg])
    } catch (err) {
      setMessages(prev => [...prev, {
        id: `err_${Date.now()}`,
        role: 'bot',
        text: `⚠️ I couldn't connect to the server right now. Please try again in a moment, or visit [iitjammu.ac.in](https://www.iitjammu.ac.in) directly.`,
        timestamp: new Date(),
        sources: [],
        isError: true,
      }])
    } finally {
      setLoading(false)
    }
  }

  const clearChat = () => {
    setMessages([WELCOME_MSG])
    setUnread(0)
  }

  return (
    <>
      {/* Floating trigger button */}
      <button
        className={`${styles.fab} ${open ? styles.fabOpen : ''}`}
        onClick={open ? handleClose : handleOpen}
        aria-label="Open AI Assistant"
        title="IIT Jammu AI Assistant"
      >
        {open ? (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        ) : (
          <>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
              <path d="M12 2C6.48 2 2 5.92 2 10.7c0 2.7 1.38 5.1 3.56 6.75L4 21l4.5-2.05C9.6 19.3 10.77 19.5 12 19.5c5.52 0 10-3.92 10-8.8C22 5.92 17.52 2 12 2z"
                fill="currentColor" opacity="0.9"/>
              <circle cx="8.5" cy="10.5" r="1.2" fill="white"/>
              <circle cx="12" cy="10.5" r="1.2" fill="white"/>
              <circle cx="15.5" cy="10.5" r="1.2" fill="white"/>
            </svg>
            {unread > 0 && (
              <span className={styles.badge}>{unread}</span>
            )}
          </>
        )}
      </button>

      {/* Chat window */}
      <div className={`${styles.windowWrap} ${open ? styles.windowOpen : ''}`}>
        {open && (
          <ChatWindow
            messages={messages}
            loading={loading}
            suggestions={suggestions}
            onSend={sendMessage}
            onClose={handleClose}
            onClear={clearChat}
          />
        )}
      </div>
    </>
  )
}
