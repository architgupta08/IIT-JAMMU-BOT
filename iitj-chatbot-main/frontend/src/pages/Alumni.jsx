import React from 'react'
import styles from './InfoPage.module.css'

const ALUMNI_STATS = [
  { n:'2000+', l:'Alumni Network' },
  { n:'8',     l:'Graduating Batches' },
  { n:'40+',   l:'Countries' },
  { n:'15+',   l:'Alumni Chapters' },
]

export default function Alumni() {
  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <div className={styles.heroBg} style={{background:'linear-gradient(135deg,#0d2137,#003366)'}} />
        <div className={styles.heroGrid} />
        <div className={`${styles.heroContent} container`}>
          <span className="label" style={{color:'#c5972a'}}>Community</span>
          <h1>Alumni Network</h1>
          <p>Connecting IIT Jammu graduates across the globe</p>
        </div>
      </div>

      <div className={`${styles.body}`}>
        <div className="container">
          <div style={{display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:16, marginBottom:48}}>
            {ALUMNI_STATS.map(s => (
              <div key={s.l} style={{background:'var(--navy)', borderRadius:14, padding:'24px', textAlign:'center'}}>
                <div style={{fontFamily:'var(--font-display)', fontSize:'2.2rem', color:'var(--gold)', marginBottom:4}}>{s.n}</div>
                <div style={{fontSize:'.72rem', fontWeight:600, letterSpacing:'.1em', textTransform:'uppercase', color:'rgba(255,255,255,.5)'}}>{s.l}</div>
              </div>
            ))}
          </div>

          <div className={styles.grid} style={{marginBottom:32}}>
            <div className={styles.card}>
              <h3>🎓 Alumni Services</h3>
              <ul>
                <li>Alumni directory & networking portal</li>
                <li>Job board for fellow alumni</li>
                <li>Mentorship programme for students</li>
                <li>Alumni Achievers recognition</li>
                <li>Annual Alumni Meet</li>
              </ul>
            </div>
            <div className={styles.card}>
              <h3>🌍 Global Chapters</h3>
              <ul>
                <li>Delhi NCR Chapter</li>
                <li>Bangalore Chapter</li>
                <li>Mumbai Chapter</li>
                <li>Hyderabad Chapter</li>
                <li>USA / North America Chapter</li>
              </ul>
            </div>
            <div className={styles.card}>
              <h3>🤝 Give Back</h3>
              <ul>
                <li>Endow scholarships for students</li>
                <li>Fund research labs & equipment</li>
                <li>Guest lectures & industry talks</li>
                <li>Internship & placement support</li>
                <li>Alumni Fellows programme</li>
              </ul>
            </div>
          </div>

          <div className={styles.card} style={{background:'var(--off-white,#f8f9fb)', border:'none'}}>
            <h3>📬 Stay Connected</h3>
            <p>Contact the Alumni Relations Office: <strong>alumni@iitjammu.ac.in</strong><br/>
            For alumni registration, visit the official alumni portal at <strong>iitjammu.ac.in/alumni</strong></p>
          </div>

          <div className={styles.aiPrompt}>
            <span className={styles.aiPromptIcon}>🤖</span>
            <span>Questions about alumni events or mentorship? Ask the AI Assistant!</span>
          </div>
        </div>
      </div>
    </div>
  )
}
