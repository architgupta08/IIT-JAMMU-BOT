import React, { useState } from 'react'
import styles from './InfoPage.module.css'

const NOTICES = [
  { cat:'Admission',  date:'15 Mar 2025', title:'B.Tech 2025 Admissions — JoSAA Registration begins 15 June 2025',     tag:'Important' },
  { cat:'Academic',   date:'10 Mar 2025', title:'End Semester Examinations Schedule — Even Semester 2024-25',           tag:'Exam' },
  { cat:'Tender',     date:'08 Mar 2025', title:'Procurement of High Performance Computing Equipment — Agastya-II',     tag:'Tender' },
  { cat:'Admission',  date:'05 Mar 2025', title:'Ph.D Admissions August 2025 — Application Portal Now Open',           tag:'New' },
  { cat:'Academic',   date:'01 Mar 2025', title:'Academic Calendar Even Semester 2024-25 — Revised Schedule',          tag:'Updated' },
  { cat:'Placement',  date:'25 Feb 2025', title:'Placement 2025: Company Registration Open for Campus Recruitment',     tag:'Placement' },
  { cat:'Tender',     date:'20 Feb 2025', title:'Housekeeping Services Rate Contract 2025-26',                         tag:'Tender' },
  { cat:'General',    date:'15 Feb 2025', title:'Anti-Ragging Committee Constitution 2024-25',                         tag:'General' },
  { cat:'Admission',  date:'10 Feb 2025', title:'M.Tech 2025 Admissions — Applications invited from GATE qualified candidates', tag:'New' },
  { cat:'Academic',   date:'05 Feb 2025', title:'DUGC Meeting Notice — Agenda for 15th February 2025',                 tag:'Meeting' },
  { cat:'Tender',     date:'01 Feb 2025', title:'Annual Rate Contract for Laboratory Chemicals and Glassware',         tag:'Tender' },
  { cat:'General',    date:'28 Jan 2025', title:'Republic Day Celebration — Programme Schedule IIT Jammu',             tag:'Event' },
]

const CATS = ['All', 'Admission', 'Academic', 'Tender', 'Placement', 'General']
const TAG_COLORS = { Important:'#c53030', New:'#276749', Updated:'#744210', Tender:'#2c5282', Placement:'#553c9a', Exam:'#702459', Meeting:'#2d3748', General:'#4a5568', Event:'#1a4731' }

export default function Notices() {
  const [cat, setCat] = useState('All')
  const filtered = cat === 'All' ? NOTICES : NOTICES.filter(n => n.cat === cat)

  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <div className={styles.heroBg} style={{background:'linear-gradient(135deg,#1a1a2e,#003366)'}} />
        <div className={styles.heroGrid} />
        <div className={`${styles.heroContent} container`}>
          <span className="label" style={{color:'#c5972a'}}>Updates</span>
          <h1>Notices &amp; Circulars</h1>
          <p>Official announcements, tenders, academic notices, and circulars</p>
        </div>
      </div>

      <div className={`${styles.body}`}>
        <div className="container">
          {/* Category filter */}
          <div style={{display:'flex', gap:8, flexWrap:'wrap', marginBottom:28}}>
            {CATS.map(c => (
              <button key={c} onClick={() => setCat(c)} style={{
                padding:'7px 18px', borderRadius:20, border:'1.5px solid',
                borderColor: cat===c ? 'var(--navy)' : 'var(--gray-200,#e4e9f0)',
                background: cat===c ? 'var(--navy)' : 'var(--white)',
                color: cat===c ? 'white' : 'var(--text-muted)',
                fontFamily:'var(--font-body)', fontSize:'.8rem', fontWeight:600,
                cursor:'pointer', transition:'all .15s',
              }}>{c}</button>
            ))}
          </div>

          <div style={{display:'flex', flexDirection:'column', border:'1px solid var(--gray-200,#e4e9f0)', borderRadius:14, overflow:'hidden'}}>
            {filtered.map((n, i) => (
              <div key={i} style={{
                display:'flex', gap:16, alignItems:'center',
                padding:'14px 20px',
                borderBottom: i < filtered.length-1 ? '1px solid var(--gray-100,#f1f4f8)' : 'none',
                background:'var(--white)', transition:'background .15s',
              }}
              onMouseEnter={e=>e.currentTarget.style.background='var(--gray-100,#f1f4f8)'}
              onMouseLeave={e=>e.currentTarget.style.background='var(--white)'}
              >
                <span style={{
                  flexShrink:0, padding:'2px 8px', borderRadius:4,
                  background: `${TAG_COLORS[n.tag] || '#4a5568'}18`,
                  color: TAG_COLORS[n.tag] || '#4a5568',
                  fontSize:'.65rem', fontWeight:700, letterSpacing:'.08em', textTransform:'uppercase',
                  minWidth:68, textAlign:'center',
                }}>{n.tag}</span>
                <span style={{fontSize:'.72rem', color:'var(--gold)', fontWeight:600, minWidth:80, flexShrink:0}}>{n.date}</span>
                <span style={{flex:1, fontSize:'.88rem', color:'var(--text)', fontWeight:500}}>{n.title}</span>
                <span style={{flexShrink:0, fontSize:'.75rem', color:'var(--navy)', fontWeight:600}}>View →</span>
              </div>
            ))}
          </div>

          <div className={styles.aiPrompt} style={{marginTop:24}}>
            <span className={styles.aiPromptIcon}>🤖</span>
            <span>Looking for a specific notice or tender? <strong>Ask the AI Assistant</strong> — it can help find what you need!</span>
          </div>
        </div>
      </div>
    </div>
  )
}
