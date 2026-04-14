import React, { useState } from 'react'
import styles from './InfoPage.module.css'

const PROGRAMS_DATA = {
  btech: {
    label: 'B.Tech', emoji: '⚙️',
    duration: '4 Years', seats: '~450 total',
    entry: 'JEE Advanced → JoSAA Counselling',
    branches: [
      { name: 'Computer Science & Engineering', seats: 75 },
      { name: 'Electrical Engineering', seats: 75 },
      { name: 'Mechanical Engineering', seats: 75 },
      { name: 'Civil Engineering', seats: 50 },
      { name: 'Chemical Engineering', seats: 30 },
      { name: 'Mathematics & Computing', seats: 40 },
      { name: 'Engineering Physics', seats: 20 },
    ],
    fees: {
      general: '₹1,51,720 / year',
      scst: '₹51,720 / year',
      hostel: '₹41,320–60,230 / year',
      onetime: '₹12,600 (one-time at admission)',
    },
    eligibility: 'Class 12 with PCM. Valid JEE Advanced rank. Age ≤ 25 years (30 for SC/ST/PwD).',
  },
  mtech: {
    label: 'M.Tech', emoji: '🔬',
    duration: '2 Years', seats: '~200 total',
    entry: 'GATE Score → Institute Admission',
    branches: [
      { name: 'VLSI Design', seats: 18 },
      { name: 'Communication Engineering', seats: 18 },
      { name: 'Thermal Engineering', seats: 18 },
      { name: 'Structural Engineering', seats: 18 },
      { name: 'Computer Science & Engg.', seats: 20 },
      { name: 'Power Electronics & Drives', seats: 18 },
      { name: 'Chemical Engineering', seats: 18 },
      { name: 'Engineering Physics', seats: 12 },
      { name: 'Mathematics & Computing', seats: 16 },
      { name: 'Materials Science & Engg.', seats: 18 },
      { name: 'Geotechnical Engineering', seats: 18 },
    ],
    fees: {
      general: '₹1,03,220 total (over 2 years)',
      scst: '₹3,220 total (over 2 years)',
      hostel: '₹41,320–60,230 / year',
      stipend: '₹12,400/month (GATE scholars with TA)',
    },
    eligibility: 'B.E./B.Tech in relevant branch. Valid GATE score required. Sponsored candidates also considered.',
  },
  msc: {
    label: 'M.Sc', emoji: '📐',
    duration: '2 Years', seats: '~80 total',
    entry: 'IIT JAM → JoSAA/CCMN',
    branches: [
      { name: 'Mathematics', seats: 40 },
      { name: 'Chemistry', seats: 40 },
    ],
    fees: {
      general: '₹1,51,720 / year',
      scst: '₹51,720 / year',
      hostel: '₹41,320–60,230 / year',
    },
    eligibility: "Bachelor's degree with relevant major. Valid IIT JAM score. Min 55% marks (50% for SC/ST).",
  },
  phd: {
    label: 'Ph.D', emoji: '🎓',
    duration: '4–6 Years', seats: 'Rolling admissions',
    entry: 'Direct application → Interview',
    branches: [
      { name: 'Computer Science & Engg.' },
      { name: 'Electrical Engineering' },
      { name: 'Mechanical Engineering' },
      { name: 'Civil Engineering' },
      { name: 'Chemical Engineering' },
      { name: 'Mathematics' },
      { name: 'Physics' },
      { name: 'Chemistry' },
      { name: 'Humanities & Social Sciences' },
      { name: 'Materials Engineering' },
      { name: 'Biosciences & Bioengineering' },
      { name: 'Interdisciplinary' },
    ],
    fees: {
      general: '₹86,580–3,27,120 (varies by category & semester)',
      scst: 'Partial fee waiver available',
      stipend: 'PMRF: ₹70,000/month; Regular: ₹31,000–35,000/month',
    },
    eligibility: "Master's degree in relevant field. GATE/NET/UGC-JRF preferred. Interview mandatory.",
  },
}

const TABS = ['btech', 'mtech', 'msc', 'phd']

export default function Programs() {
  const [active, setActive] = useState('btech')
  const prog = PROGRAMS_DATA[active]

  return (
    <div className={styles.page}>
      <div className={styles.pageHero} style={{ background: 'linear-gradient(135deg,#003366,#0a4a8a)' }}>
        <div className="container">
          <span className="badge">Academics</span>
          <h1>Academic Programs</h1>
          <p>World-class engineering & science education at IIT Jammu</p>
        </div>
      </div>

      <div className="container section-pad">
        {/* Tab bar */}
        <div className={styles.tabs}>
          {TABS.map(tab => (
            <button
              key={tab}
              className={`${styles.tab} ${active === tab ? styles.tabActive : ''}`}
              onClick={() => setActive(tab)}
            >
              {PROGRAMS_DATA[tab].emoji} {PROGRAMS_DATA[tab].label}
            </button>
          ))}
        </div>

        {/* Program detail */}
        <div className={styles.progDetail}>
          <div className={styles.progMeta}>
            <div className={styles.metaItem}><strong>Duration</strong><span>{prog.duration}</span></div>
            <div className={styles.metaItem}><strong>Total Seats</strong><span>{prog.seats}</span></div>
            <div className={styles.metaItem}><strong>Admission</strong><span>{prog.entry}</span></div>
          </div>

          <div className={styles.progGrid}>
            {/* Branches */}
            <div className={styles.card}>
              <h3>🏫 Branches / Specializations</h3>
              <ul className={styles.branchList}>
                {prog.branches.map(b => (
                  <li key={b.name}>
                    <span>{b.name}</span>
                    {b.seats && <span className={styles.seats}>{b.seats} seats</span>}
                  </li>
                ))}
              </ul>
            </div>

            <div className={styles.rightCol}>
              {/* Fees */}
              <div className={styles.card}>
                <h3>💰 Fee Structure</h3>
                <table className={styles.feeTable}>
                  <tbody>
                    {Object.entries(prog.fees).map(([k, v]) => (
                      <tr key={k}>
                        <td>{k === 'general' ? 'General/OBC/EWS' : k === 'scst' ? 'SC/ST/PwD' : k.charAt(0).toUpperCase() + k.slice(1)}</td>
                        <td><strong>{v}</strong></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Eligibility */}
              <div className={styles.card}>
                <h3>✅ Eligibility</h3>
                <p style={{ fontSize: 14, color: '#475569', lineHeight: 1.7 }}>{prog.eligibility}</p>
              </div>
            </div>
          </div>

          <div className={styles.aiPrompt}>
            <span>🤖</span>
            <span>Have more questions about {prog.label} at IIT Jammu? <strong>Ask our AI Assistant</strong> — click the chat button in the bottom right!</span>
          </div>
        </div>
      </div>
    </div>
  )
}
