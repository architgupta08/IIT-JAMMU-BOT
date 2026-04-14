import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import styles from './InfoPage.module.css'

const DEPTS = [
  { id:'cse',    icon:'💻', name:'Computer Science & Engineering',   hod:'Prof. Rakesh Kumar',  faculty:22, labs:8,  research:'AI/ML, Cybersecurity, Networks, Vision' },
  { id:'ee',     icon:'⚡', name:'Electrical Engineering',           hod:'Prof. Ankush Mittal', faculty:18, labs:7,  research:'Power Systems, VLSI, Signal Processing' },
  { id:'me',     icon:'⚙️', name:'Mechanical Engineering',           hod:'Prof. Vishal Sharma', faculty:16, labs:9,  research:'Thermal, Manufacturing, Robotics, CAD/CAM' },
  { id:'ce',     icon:'🏗️', name:'Civil Engineering',               hod:'Prof. Deepak Bhatia', faculty:14, labs:6,  research:'Structural, Geotechnical, Transportation, Water' },
  { id:'che',    icon:'⚗️', name:'Chemical Engineering',             hod:'Prof. Neeraj Tiwari', faculty:12, labs:6,  research:'Reaction Engineering, Process Control, Polymers' },
  { id:'math',   icon:'∑',  name:'Mathematics',                      hod:'Prof. A. Kumar',      faculty:14, labs:2,  research:'Algebra, Analysis, Optimization, Cryptography' },
  { id:'physics',icon:'🔭', name:'Physics',                          hod:'Prof. R. Sharma',     faculty:12, labs:5,  research:'Photonics, Condensed Matter, Laser Physics' },
  { id:'chem',   icon:'🧪', name:'Chemistry',                        hod:'Prof. S. Singh',      faculty:11, labs:7,  research:'Organic Synthesis, Materials Chemistry, Nano' },
  { id:'hss',    icon:'📖', name:'Humanities & Social Sciences',     hod:'Prof. B. Bajaj',      faculty:14, labs:2,  research:'Economics, Linguistics, Psychology, Management' },
  { id:'mat',    icon:'🔩', name:'Materials Engineering',            hod:'Prof. K. Joshi',      faculty:9,  labs:5,  research:'Composites, Nanomaterials, Biomaterials' },
  { id:'bsbe',   icon:'🧬', name:'Biosciences & Bioengineering',     hod:'Prof. M. Patel',      faculty:10, labs:6,  research:'Computational Bio, Biomedical Devices, Genomics' },
  { id:'idp',    icon:'🎯', name:'Interdisciplinary Programme',      hod:'Coord. Committee',    faculty:30, labs:4,  research:'Cross-disciplinary research, Industry projects' },
]

export default function Departments() {
  const [active, setActive] = useState(null)
  const selected = active ? DEPTS.find(d => d.id === active) : null

  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <div className={styles.heroBg} style={{background:'linear-gradient(135deg,#001e3c,#003366)'}} />
        <div className={styles.heroGrid} />
        <div className={`${styles.heroContent} container`}>
          <span className="label" style={{color:'#c5972a'}}>Academic Units</span>
          <h1>Departments</h1>
          <p>12 academic departments covering engineering, science, and humanities</p>
        </div>
      </div>

      <div className={`${styles.body}`}>
        <div className="container">
          <div style={{display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:16, marginBottom:32}}>
            {DEPTS.map(d => (
              <button
                key={d.id}
                id={d.id}
                onClick={() => setActive(active === d.id ? null : d.id)}
                style={{
                  display:'flex', gap:14, alignItems:'flex-start',
                  padding:'20px', borderRadius:14, border:'1px solid',
                  borderColor: active===d.id ? 'var(--navy)' : 'var(--gray-200,#e4e9f0)',
                  background: active===d.id ? 'var(--navy,#003366)' : 'var(--white)',
                  cursor:'pointer', textAlign:'left', transition:'all .2s',
                  boxShadow: active===d.id ? '0 4px 20px rgba(0,51,102,.2)' : 'none',
                }}
              >
                <span style={{fontSize:'1.6rem', lineHeight:1}}>{d.icon}</span>
                <div>
                  <div style={{
                    fontFamily:'var(--font-body)', fontWeight:600, fontSize:'.88rem',
                    color: active===d.id ? 'white' : 'var(--navy,#003366)',
                    lineHeight:1.3, marginBottom:4
                  }}>{d.name}</div>
                  <div style={{fontSize:'.72rem', color: active===d.id ? 'rgba(255,255,255,.55)' : 'var(--text-muted,#5a6a7e)'}}>
                    {d.faculty} faculty · {d.labs} labs
                  </div>
                </div>
              </button>
            ))}
          </div>

          {selected && (
            <div className={styles.card} style={{borderLeft:'3px solid var(--gold,#c5972a)', marginBottom:24}}>
              <div style={{display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:24}}>
                <div>
                  <h3>{selected.icon} {selected.name}</h3>
                  <ul><li><strong>Head of Dept:</strong> {selected.hod}</li><li><strong>Faculty:</strong> {selected.faculty} members</li><li><strong>Labs:</strong> {selected.labs} active labs</li></ul>
                </div>
                <div>
                  <div style={{fontWeight:600, fontSize:'.8rem', letterSpacing:'.08em', textTransform:'uppercase', color:'var(--navy)', marginBottom:10}}>Research Focus</div>
                  <p style={{fontSize:'.88rem', color:'var(--text-muted)'}}>{selected.research}</p>
                </div>
                <div>
                  <div style={{fontWeight:600, fontSize:'.8rem', letterSpacing:'.08em', textTransform:'uppercase', color:'var(--navy)', marginBottom:10}}>Quick Links</div>
                  <div style={{display:'flex', flexDirection:'column', gap:6}}>
                    {['Faculty', 'Research', 'Programs', 'Contact'].map(l => (
                      <Link key={l} to={`/${l.toLowerCase()}`} style={{fontSize:'.84rem', color:'var(--navy)'}}>→ {l}</Link>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className={styles.aiPrompt}>
            <span className={styles.aiPromptIcon}>🤖</span>
            <span>Ask the AI about any department's research areas, faculty, or how to apply — available 24/7!</span>
          </div>
        </div>
      </div>
    </div>
  )
}
