// Admissions.jsx
import React from 'react'
import styles from './InfoPage.module.css'

export default function Admissions() {
  return (
    <div className={styles.page}>
      <div className={styles.pageHero} style={{ background: 'linear-gradient(135deg,#1a3a5c,#2d6a4f)' }}>
        <div className="container">
          <span className="badge">Admissions</span>
          <h1>Admissions 2025</h1>
          <p>Join IIT Jammu — Gateway to excellence in engineering and research</p>
        </div>
      </div>
      <div className="container section-pad">
        <div className={styles.infoGrid}>
          <div className={styles.card}>
            <h3>🎯 B.Tech Admissions</h3>
            <ul><li>Route: JEE Advanced → JoSAA</li><li>Reservation: 27% OBC, 15% SC, 7.5% ST, 10% EWS</li><li>Supernumerary: 20% girl seats</li><li>PwD: 5% horizontal</li></ul>
          </div>
          <div className={styles.card}>
            <h3>🔬 M.Tech Admissions</h3>
            <ul><li>Route: GATE Score required</li><li>Minimum GATE: Branch-specific cutoff</li><li>Interview mandatory</li><li>Sponsored candidates: No GATE needed</li></ul>
          </div>
          <div className={styles.card}>
            <h3>🎓 Ph.D Admissions</h3>
            <ul><li>Rolling admissions twice a year</li><li>GATE/NET/CSIR-JRF preferred</li><li>Written test + Interview</li><li>Fellowships: PMRF, Institute, MHRD</li></ul>
          </div>
        </div>

        <div style={{ marginTop: 36 }}>
          <h2 style={{ fontFamily: 'var(--font-heading)', color: 'var(--iitj-navy)', marginBottom: 20 }}>Admission Process</h2>
          <div className={styles.timeline}>
            {[
              { step: 'Register', desc: 'Create account on JoSAA/CCMN/Institute portal' },
              { step: 'Apply',    desc: 'Fill application form with valid score and documents' },
              { step: 'Rank List',desc: 'Merit list prepared based on entrance score' },
              { step: 'Allotment',desc: 'Seat allotment through counselling rounds' },
              { step: 'Reporting',desc: 'Report to institute with required documents' },
              { step: 'Enroll',   desc: 'Fee payment and academic registration' },
            ].map((item, i) => (
              <div key={i} className={styles.timelineItem}>
                <div className={styles.timelineNum}>{i + 1}</div>
                <div className={styles.timelineContent}>
                  <h4>{item.step}</h4>
                  <p>{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className={styles.card} style={{ marginTop: 28 }}>
          <h3>💰 Scholarships & Financial Aid</h3>
          <table className={styles.feeTable}>
            <tbody>
              <tr><td>Merit-cum-Means (MCM)</td><td><strong>Full fee waiver + ₹1,000/month</strong></td></tr>
              <tr><td>Free Studentship (SC/ST)</td><td><strong>Full tuition fee waiver</strong></td></tr>
              <tr><td>IITJ Need-based Scholarship</td><td><strong>Up to ₹50,000/year</strong></td></tr>
              <tr><td>PMRF Fellowship (Ph.D)</td><td><strong>₹70,000–80,000/month</strong></td></tr>
            </tbody>
          </table>
        </div>

        <div className={styles.aiPrompt}>
          <span>🤖</span>
          <span>Questions about admission cutoffs, eligibility, or documents? <strong>Ask our AI Assistant</strong> — it knows all the details!</span>
        </div>
      </div>
    </div>
  )
}
