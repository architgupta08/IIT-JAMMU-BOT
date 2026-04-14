import React from 'react'
import styles from './InfoPage.module.css'

const LEADERSHIP = [
  { role:'Director',                 name:'Prof. Manoj Singh Gaur',   dept:'PhD, IIT Kanpur · Computer Science & Engineering', email:'director@iitjammu.ac.in' },
  { role:'Dean — Academics',        name:'Prof. [Name]',              dept:'Academic programs, curriculum, examinations',       email:'dean.academics@iitjammu.ac.in' },
  { role:'Dean — Research',         name:'Prof. [Name]',              dept:'Sponsored research, patents, IRD office',           email:'dean.research@iitjammu.ac.in' },
  { role:'Dean — Student Affairs',  name:'Prof. [Name]',              dept:'Hostels, welfare, student clubs, counselling',      email:'dean.sa@iitjammu.ac.in' },
  { role:'Dean — Faculty Affairs',  name:'Prof. [Name]',              dept:'Faculty recruitment, welfare, development',         email:'dean.fa@iitjammu.ac.in' },
  { role:'Registrar',               name:'Dr. [Name]',                dept:'Administration, legal, HR, general services',      email:'registrar@iitjammu.ac.in' },
]

const BODIES = [
  { name:'Board of Governors',    desc:'Apex governing body of the institute. Chaired by a distinguished personality. Responsible for overall policy and direction.', members:15 },
  { name:'Senate',               desc:'Academic governing body. Responsible for all academic matters — programs, examinations, degrees, research, and academic policies.', members:40 },
  { name:'Finance Committee',     desc:'Oversees the financial management, budget approval, and financial planning of the institute.', members:8 },
  { name:'Building & Works Committee', desc:'Responsible for campus construction, infrastructure development, and maintenance planning.', members:7 },
]

export default function Administration() {
  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <div className={styles.heroBg} style={{background:'linear-gradient(135deg,#1a2a4a,#003366)'}} />
        <div className={styles.heroGrid} />
        <div className={`${styles.heroContent} container`}>
          <span className="label" style={{color:'#c5972a'}}>Governance</span>
          <h1>Administration</h1>
          <p>Leadership and governing bodies of IIT Jammu</p>
        </div>
      </div>

      <div className={`${styles.body}`}>
        <div className="container">
          <span className="label">Leadership</span>
          <h2 style={{marginBottom:24}}>Institute Leadership</h2>
          <div style={{display:'flex', flexDirection:'column', gap:12, marginBottom:48}}>
            {LEADERSHIP.map(l => (
              <div key={l.role} className={styles.card} style={{display:'flex', alignItems:'center', gap:24, padding:'20px 24px'}}>
                <div style={{width:52, height:52, borderRadius:'50%', background:'linear-gradient(135deg,#003366,#0a5299)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0}}>
                  <span style={{color:'white', fontSize:'1.2rem'}}>👤</span>
                </div>
                <div style={{flex:1}}>
                  <div style={{fontSize:'.7rem', fontWeight:700, letterSpacing:'.1em', textTransform:'uppercase', color:'var(--gold)', marginBottom:3}}>{l.role}</div>
                  <div style={{fontWeight:600, fontSize:'.95rem', color:'var(--navy)', marginBottom:2}}>{l.name}</div>
                  <div style={{fontSize:'.8rem', color:'var(--text-muted)'}}>{l.dept}</div>
                </div>
                <a href={`mailto:${l.email}`} style={{fontSize:'.78rem', color:'var(--navy)', fontWeight:500}}>✉ {l.email}</a>
              </div>
            ))}
          </div>

          <span className="label">Governance</span>
          <h2 style={{marginBottom:24}}>Governing Bodies</h2>
          <div className={styles.grid2} style={{marginBottom:32}}>
            {BODIES.map(b => (
              <div key={b.name} className={styles.card}>
                <h3>🏛️ {b.name}</h3>
                <p>{b.desc}</p>
                <div style={{marginTop:12, fontSize:'.78rem', color:'var(--gold)', fontWeight:600}}>{b.members} members</div>
              </div>
            ))}
          </div>

          <div className={styles.aiPrompt}>
            <span className={styles.aiPromptIcon}>🤖</span>
            <span>Need specific contact details for any administrative office? <strong>Ask the AI Assistant</strong></span>
          </div>
        </div>
      </div>
    </div>
  )
}
