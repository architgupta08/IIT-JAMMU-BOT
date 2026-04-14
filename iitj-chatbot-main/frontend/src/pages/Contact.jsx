import React from 'react'
import styles from './InfoPage.module.css'

export default function Contact() {
  return (
    <div className={styles.page}>
      <div className={styles.pageHero} style={{ background:'linear-gradient(135deg,#2d1b69,#11998e)' }}>
        <div className="container">
          <span className="badge">Get In Touch</span>
          <h1>Contact Us</h1>
          <p>We're here to help — reach out to the right office</p>
        </div>
      </div>

      <div className="container section-pad">
        <div className={styles.infoGrid}>
          <div className={styles.card}>
            <h3>📍 Main Address</h3>
            <p>
              Indian Institute of Technology Jammu<br />
              Jagti, P.O. Nagrota<br />
              Jammu — 181221<br />
              Jammu & Kashmir, India
            </p>
            <p style={{ marginTop:12 }}>
              📞 +91-191-257-0066<br />
              ✉️ info@iitjammu.ac.in
            </p>
          </div>

          <div className={styles.card}>
            <h3>🎓 Academic / Admissions</h3>
            <p>
              <strong>Dean of Academics:</strong><br />
              dean.academics@iitjammu.ac.in<br /><br />
              <strong>Admission Office:</strong><br />
              admissions@iitjammu.ac.in<br />
              +91-191-257-0066 (Extn. 2001)
            </p>
          </div>

          <div className={styles.card}>
            <h3>💼 Placements</h3>
            <p>
              <strong>Training & Placement Cell:</strong><br />
              placements@iitjammu.ac.in<br /><br />
              <strong>Placement Officer:</strong><br />
              +91-191-257-0066 (Extn. 2010)<br /><br />
              For company registrations:<br />
              companies.placement@iitjammu.ac.in
            </p>
          </div>

          <div className={styles.card}>
            <h3>🔬 Research & Sponsored Projects</h3>
            <p>
              <strong>Dean of Research:</strong><br />
              dean.research@iitjammu.ac.in<br /><br />
              <strong>IRD Office:</strong><br />
              ird@iitjammu.ac.in
            </p>
          </div>

          <div className={styles.card}>
            <h3>🏠 Hostel & Student Affairs</h3>
            <p>
              <strong>Dean of Student Affairs:</strong><br />
              dean.sa@iitjammu.ac.in<br /><br />
              <strong>Chief Warden:</strong><br />
              chiefwarden@iitjammu.ac.in<br /><br />
              <strong>Medical Centre:</strong><br />
              medical@iitjammu.ac.in
            </p>
          </div>

          <div className={styles.card}>
            <h3>🚗 How to Reach</h3>
            <ul>
              <li><strong>By Air:</strong> Jammu Airport (~20 km)</li>
              <li><strong>By Train:</strong> Jammu Tawi Station (~18 km)</li>
              <li><strong>By Road:</strong> NH-44, Jammu–Srinagar Highway</li>
              <li><strong>Bus:</strong> RSRDC buses from Jammu city</li>
              <li><strong>Taxi/Auto:</strong> Available from city</li>
            </ul>
          </div>
        </div>

        <div className={styles.aiPrompt} style={{ marginTop:28 }}>
          <span>🤖</span>
          <span>Need a specific office's contact? <strong>Ask the AI Assistant</strong> — it can find any department contact in seconds!</span>
        </div>
      </div>
    </div>
  )
}
