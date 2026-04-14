import React from 'react'
import { Link } from 'react-router-dom'
import styles from './Footer.module.css'

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.top}>
        <div className={styles.col}>
          <h3>IIT Jammu</h3>
          <p>Indian Institute of Technology Jammu<br />
            Jagti, Nagrota, Jammu — 181221<br />
            Jammu & Kashmir, India
          </p>
          <p style={{ marginTop: 10, fontSize: 13 }}>
            📞 +91-191-257-0066<br />
            ✉️ info@iitjammu.ac.in
          </p>
        </div>
        <div className={styles.col}>
          <h3>Quick Links</h3>
          <ul>
            <li><Link to="/about">About IIT Jammu</Link></li>
            <li><Link to="/programs">Academic Programs</Link></li>
            <li><Link to="/admissions">Admissions</Link></li>
            <li><Link to="/faculty">Faculty</Link></li>
            <li><Link to="/placements">Placements</Link></li>
          </ul>
        </div>
        <div className={styles.col}>
          <h3>Academics</h3>
          <ul>
            <li><Link to="/programs">B.Tech Programs</Link></li>
            <li><Link to="/programs">M.Tech Programs</Link></li>
            <li><Link to="/programs">Ph.D Programs</Link></li>
            <li><Link to="/research">Research Centers</Link></li>
            <li><Link to="/campus">Library</Link></li>
          </ul>
        </div>
        <div className={styles.col}>
          <h3>Student Info</h3>
          <ul>
            <li><Link to="/admissions">Fee Structure</Link></li>
            <li><Link to="/admissions">Scholarships</Link></li>
            <li><Link to="/campus">Hostels</Link></li>
            <li><Link to="/campus">Facilities</Link></li>
            <li><Link to="/contact">Contact Us</Link></li>
          </ul>
        </div>
      </div>
      <div className={styles.bottom}>
        <span>
          © 2024 Indian Institute of Technology Jammu.
          <span className={styles.note}> &nbsp;·&nbsp; This is a demo site for educational purposes. AI Assistant powered by Google Gemini.</span>
        </span>
        <span className={styles.credit}>
          Built with ❤️ using VectorlessRAG + Gemini
        </span>
      </div>
    </footer>
  )
}
