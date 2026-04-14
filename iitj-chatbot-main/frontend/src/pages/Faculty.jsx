import React from 'react'
import styles from './InfoPage.module.css'
export default function Faculty() {
  const FACULTY = [
    { name:'Prof. Manoj Singh Gaur', dept:'Director, CSE', initial:'MG' },
    { name:'Prof. Rakesh Kumar',     dept:'Computer Sci. & Engg.',  initial:'RK' },
    { name:'Prof. Ankush Mittal',    dept:'Electrical Engg.',       initial:'AM' },
    { name:'Prof. Vishal Sharma',    dept:'Mechanical Engg.',       initial:'VS' },
    { name:'Prof. Sunita Srivastava',dept:'Mathematics',            initial:'SS' },
    { name:'Prof. Arun Kumar',       dept:'Physics',                initial:'AK' },
    { name:'Prof. Neeraj Tiwari',    dept:'Chemical Engg.',         initial:'NT' },
    { name:'Prof. Bhavna Bajaj',     dept:'Humanities & SS',        initial:'BB' },
    { name:'Prof. Deepak Bhatia',    dept:'Civil Engg.',            initial:'DB' },
  ]
  return (
    <div className={styles.page}>
      <div className={styles.pageHero} style={{ background:'linear-gradient(135deg,#1e3a5f,#1a5276)' }}>
        <div className="container"><span className="badge">People</span><h1>Faculty</h1><p>Distinguished researchers and educators at IIT Jammu</p></div>
      </div>
      <div className="container section-pad">
        <div className={styles.infoGrid} style={{ marginBottom:28 }}>
          <div className={styles.card}><h3>📊 Faculty Stats</h3><ul><li>150+ Permanent Faculty</li><li>24 Adjunct Faculty</li><li>PhD from top institutes worldwide</li><li>Active in 40+ research groups</li></ul></div>
          <div className={styles.card}><h3>🏛️ Departments</h3><ul><li>Computer Science & Engineering</li><li>Electrical Engineering</li><li>Mechanical Engineering</li><li>Civil Engineering</li><li>Mathematics, Physics, Chemistry</li></ul></div>
          <div className={styles.card}><h3>🔬 Research Focus</h3><ul><li>AI & Machine Learning</li><li>Power Systems & VLSI</li><li>Structural & Geo-tech Engg.</li><li>Computational Science</li><li>Biomedical Engineering</li></ul></div>
        </div>
        <h2 style={{ fontFamily:'var(--font-heading)', color:'var(--iitj-navy)', marginBottom:20 }}>Faculty Highlights</h2>
        <div className={styles.facultyGrid}>
          {FACULTY.map(f => (
            <div key={f.name} className={styles.facultyCard}>
              <div className={styles.facultyAvatar}>{f.initial}</div>
              <div className={styles.facultyInfo}>
                <h4>{f.name}</h4>
                <p>{f.dept}</p>
              </div>
            </div>
          ))}
        </div>
        <div className={styles.aiPrompt} style={{ marginTop:28 }}>
          <span>🤖</span>
          <span>Looking for a specific faculty member's research interests or contact? <strong>Ask the AI Assistant!</strong></span>
        </div>
      </div>
    </div>
  )
}
