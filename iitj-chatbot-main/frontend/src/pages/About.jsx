import React from 'react'
import styles from './InfoPage.module.css'

export default function About() {
  return (
    <div className={styles.page}>
      <div className={styles.pageHero} style={{ background: 'linear-gradient(135deg,#003366,#1a5276)' }}>
        <div className="container">
          <span className="badge">About</span>
          <h1>About IIT Jammu</h1>
          <p>A premier Institute of National Importance in Jammu & Kashmir</p>
        </div>
      </div>

      <div className="container section-pad">
        <div style={{ display:'grid', gridTemplateColumns:'2fr 1fr', gap:40, marginBottom:40, alignItems:'start' }}>
          <div>
            <h2 style={{ fontFamily:'var(--font-heading)', color:'var(--iitj-navy)', fontSize:28, marginBottom:16 }}>Our Story</h2>
            <p style={{ color:'#475569', lineHeight:1.8, marginBottom:14 }}>
              IIT Jammu was established in 2016 by an Act of Parliament as one of the new IITs in the country.
              It is mentored by IIT Delhi and has rapidly grown into a fully functional institute with state-of-the-art infrastructure.
            </p>
            <p style={{ color:'#475569', lineHeight:1.8, marginBottom:14 }}>
              Located at Jagti in the Nagrota area of Jammu, the institute spans over 250 acres. The permanent campus
              is being developed with world-class academic blocks, research labs, hostels, sports facilities, and a central library.
            </p>
            <p style={{ color:'#475569', lineHeight:1.8 }}>
              IIT Jammu is committed to providing quality education in engineering, science, and technology,
              and to undertaking research, development, and innovation in the frontiers of knowledge.
            </p>
          </div>
          <div className={styles.card}>
            <h3>🏛️ Key Facts</h3>
            <table className={styles.feeTable}>
              <tbody>
                {[
                  ['Established','2016'],
                  ['Mentor Institute','IIT Delhi'],
                  ['Campus Area','250+ Acres'],
                  ['Location','Jagti, Nagrota, Jammu'],
                  ['Students','4900+'],
                  ['Faculty','150+'],
                  ['Departments','12+'],
                  ['NIRF Rank','#51–75 (2024)'],
                ].map(([k,v]) => (
                  <tr key={k}><td style={{ color:'#64748b' }}>{k}</td><td><strong>{v}</strong></td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className={styles.infoGrid}>
          <div className={styles.card}>
            <h3>🎯 Vision</h3>
            <p>To be a global leader in technology education and research, contributing to the socio-economic development of India and beyond.</p>
          </div>
          <div className={styles.card}>
            <h3>💡 Mission</h3>
            <ul>
              <li>Provide quality technical education</li>
              <li>Foster research and innovation</li>
              <li>Promote entrepreneurship</li>
              <li>Serve the nation and humanity</li>
            </ul>
          </div>
          <div className={styles.card}>
            <h3>🏆 Recognitions</h3>
            <ul>
              <li>NIRF ranked institute</li>
              <li>Institute of National Importance</li>
              <li>Fully funded by Ministry of Education</li>
              <li>Atal Innovation Mission partner</li>
            </ul>
          </div>
        </div>

        <div className={styles.aiPrompt} style={{ marginTop:28 }}>
          <span>🤖</span>
          <span>Ask the AI Assistant anything about IIT Jammu's history, leadership, rankings, or achievements!</span>
        </div>
      </div>
    </div>
  )
}
