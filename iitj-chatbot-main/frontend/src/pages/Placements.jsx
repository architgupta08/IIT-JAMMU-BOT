import React from 'react'
import styles from './InfoPage.module.css'

const STATS = [
  { label: 'Students Placed', value: '320+', sub: '2023–24' },
  { label: 'Highest CTC', value: '₹1.09 Cr', sub: 'per annum' },
  { label: 'Average CTC', value: '₹16.4 LPA', sub: '2023–24' },
  { label: 'Companies Visited', value: '120+', sub: 'each year' },
]

const COMPANIES = [
  'Google','Microsoft','Amazon','Samsung','Qualcomm',
  'Flipkart','Walmart Labs','Goldman Sachs','JP Morgan',
  'TCS','Infosys','Wipro','DRDO','ISRO',
  'Texas Instruments','Cadence','Synopsys','L&T','Tata Motors',
  'Intel','Adobe','Cisco','Siemens','ABB',
]

export default function Placements() {
  return (
    <div className={styles.page}>
      <div className={styles.pageHero} style={{ background: 'linear-gradient(135deg,#1a1a2e,#16213e)' }}>
        <div className="container">
          <span className="badge">Careers</span>
          <h1>Placements</h1>
          <p>IIT Jammu graduates excel at top global companies</p>
        </div>
      </div>

      <div className="container section-pad">
        {/* Stats row */}
        <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:16, marginBottom:36 }}>
          {STATS.map(s => (
            <div key={s.label} className={styles.card} style={{ textAlign:'center' }}>
              <div style={{ fontFamily:'var(--font-heading)', fontSize:34, fontWeight:700, color:'var(--iitj-gold)' }}>{s.value}</div>
              <div style={{ fontFamily:'var(--font-heading)', fontSize:13, fontWeight:600, color:'var(--iitj-navy)', marginTop:4 }}>{s.label}</div>
              <div style={{ fontSize:11, color:'#94a3b8', marginTop:2 }}>{s.sub}</div>
            </div>
          ))}
        </div>

        <div className={styles.infoGrid}>
          <div className={styles.card}>
            <h3>📋 Process Overview</h3>
            <div className={styles.timeline}>
              {['Aug: Pre-placement talks & PPOs','Sep–Oct: Phase 1 (Core + IT Companies)','Nov–Dec: Phase 2 (PSUs, Finance, Analytics)','Jan–Mar: Phase 3 (Startups, remaining)'].map((s,i) => (
                <div key={i} className={styles.timelineItem} style={{ padding:'10px 0' }}>
                  <div className={styles.timelineNum} style={{ width:26, height:26, fontSize:12 }}>{i+1}</div>
                  <div className={styles.timelineContent}><p style={{ fontSize:13 }}>{s}</p></div>
                </div>
              ))}
            </div>
          </div>

          <div className={styles.card}>
            <h3>📊 Branch-wise Highlights (2024)</h3>
            <table className={styles.feeTable}>
              <thead>
                <tr>
                  <td><strong>Branch</strong></td>
                  <td style={{ textAlign:'right' }}><strong>Avg CTC</strong></td>
                </tr>
              </thead>
              <tbody>
                {[['CSE','₹22.4 LPA'],['EE','₹17.1 LPA'],['ME','₹13.5 LPA'],['CE','₹11.8 LPA'],['CHE','₹12.0 LPA'],['M&C','₹20.2 LPA']].map(([b,c]) => (
                  <tr key={b}><td>{b}</td><td><strong>{c}</strong></td></tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className={styles.card}>
            <h3>🎯 Internship Stats</h3>
            <ul>
              <li>250+ students placed for internships</li>
              <li>Stipend: ₹20,000–₹1,50,000/month</li>
              <li>PPO conversion rate: ~35%</li>
              <li>Research internships: DAAD, Mitacs, SN Bose</li>
              <li>International internships offered</li>
            </ul>
          </div>
        </div>

        {/* Companies */}
        <div className={styles.card} style={{ marginTop:24 }}>
          <h3>🏢 Recruiting Companies</h3>
          <div style={{ display:'flex', flexWrap:'wrap', gap:8, marginTop:4 }}>
            {COMPANIES.map(c => (
              <span key={c} style={{
                background:'#f0f4f8', border:'1px solid #e2e8f0',
                borderRadius:6, padding:'5px 12px',
                fontSize:12.5, color:'#334155',
                fontFamily:'var(--font-heading)', fontWeight:600,
              }}>{c}</span>
            ))}
          </div>
        </div>

        <div className={styles.aiPrompt} style={{ marginTop:24 }}>
          <span>🤖</span>
          <span>Ask the AI about placement statistics, top recruiters, or internship opportunities at IIT Jammu!</span>
        </div>
      </div>
    </div>
  )
}
