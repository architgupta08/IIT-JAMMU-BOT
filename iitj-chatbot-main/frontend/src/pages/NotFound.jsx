import React from 'react'
import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div style={{
      display:'flex', flexDirection:'column',
      alignItems:'center', justifyContent:'center',
      minHeight:'60vh', padding:'40px 20px', textAlign:'center',
    }}>
      <div style={{ fontSize:72, marginBottom:16 }}>🏛️</div>
      <h1 style={{ fontFamily:'var(--font-heading)', color:'var(--iitj-navy)', fontSize:48, marginBottom:8 }}>404</h1>
      <h2 style={{ fontFamily:'var(--font-heading)', color:'#475569', fontSize:22, marginBottom:16 }}>Page Not Found</h2>
      <p style={{ color:'#64748b', maxWidth:400, marginBottom:28 }}>
        The page you're looking for doesn't exist on this demo site. Try using the AI Assistant to find what you need!
      </p>
      <div style={{ display:'flex', gap:12, flexWrap:'wrap', justifyContent:'center' }}>
        <Link to="/" style={{
          background:'var(--iitj-navy)', color:'white',
          fontFamily:'var(--font-heading)', fontWeight:700,
          fontSize:14, letterSpacing:'0.06em',
          padding:'11px 24px', borderRadius:8,
          textDecoration:'none',
        }}>← Go Home</Link>
        <button
          onClick={() => document.querySelector('[aria-label="Open AI Assistant"]')?.click()}
          style={{
            background:'var(--iitj-gold)', color:'white',
            fontFamily:'var(--font-heading)', fontWeight:700,
            fontSize:14, letterSpacing:'0.06em',
            padding:'11px 24px', borderRadius:8,
            border:'none', cursor:'pointer',
          }}
        >💬 Ask AI Assistant</button>
      </div>
    </div>
  )
}
