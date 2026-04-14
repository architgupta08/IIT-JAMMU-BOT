import React from 'react'
import { Link } from 'react-router-dom'
import styles from './Home.module.css'

const STATS = [
  { num: '4900+', label: 'Students' },
  { num: '150+',  label: 'Faculty' },
  { num: '12',    label: 'Departments' },
  { num: '98%',   label: 'Placement Rate' },
]

const PROGRAMS = [
  { icon: '⚙️', title: 'B.Tech',   desc: '7 branches + Engg. Physics', link: '/programs' },
  { icon: '🔬', title: 'M.Tech',   desc: '11 specializations',           link: '/programs' },
  { icon: '📐', title: 'M.Sc',     desc: 'Mathematics & Chemistry',      link: '/programs' },
  { icon: '🎓', title: 'Ph.D',     desc: '12 departments',               link: '/programs' },
]

const NEWS = [
  { date: 'Nov 2024', title: 'IIT Jammu ranked in NIRF 2024 — #51-75 band' },
  { date: 'Oct 2024', title: 'New research labs inaugurated at Jagti campus' },
  { date: 'Sep 2024', title: 'IIT Jammu signs MoU with TCS for industry collaboration' },
  { date: 'Aug 2024', title: 'Placement 2024: Highest CTC ₹1.09 Crore per annum' },
]

export default function Home() {
  return (
    <div className={styles.home}>
      {/* Hero */}
      <section className={styles.hero}>
        <div className={styles.heroOverlay} />
        <div className={styles.heroBg} />
        <div className={styles.heroContent}>
          <span className={styles.heroTag}>Institute of National Importance</span>
          <h1 className={styles.heroTitle}>
            Indian Institute of<br />
            <span className={styles.heroGold}>Technology Jammu</span>
          </h1>
          <p className={styles.heroSub}>
            Advancing knowledge, fostering innovation, and building the engineers
            and researchers of tomorrow in the heart of Jammu & Kashmir.
          </p>
          <div className={styles.heroCta}>
            <Link to="/admissions" className={styles.btnPrimary}>Apply Now</Link>
            <Link to="/about"      className={styles.btnSecondary}>Explore IIT Jammu</Link>
          </div>
          <div className={styles.heroAI}>
            <div className={styles.aiPulse} />
            <span>🤖 Try our AI Assistant — ask anything in any language!</span>
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className={styles.statsBar}>
        <div className="container">
          <div className={styles.statsGrid}>
            {STATS.map(s => (
              <div key={s.label} className={styles.statItem}>
                <span className={styles.statNum}>{s.num}</span>
                <span className={styles.statLabel}>{s.label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Programs */}
      <section className={`${styles.programs} section-pad`}>
        <div className="container">
          <div className={styles.sectionHead}>
            <span className="badge">Academics</span>
            <h2>Academic Programs</h2>
            <p>World-class engineering and science education</p>
          </div>
          <div className={styles.programsGrid}>
            {PROGRAMS.map(p => (
              <Link key={p.title} to={p.link} className={styles.programCard}>
                <span className={styles.programIcon}>{p.icon}</span>
                <h3>{p.title}</h3>
                <p>{p.desc}</p>
                <span className={styles.arrow}>→</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* About strip */}
      <section className={styles.aboutStrip}>
        <div className="container">
          <div className={styles.aboutGrid}>
            <div className={styles.aboutText}>
              <span className="badge">About Us</span>
              <h2>Excellence Since 2016</h2>
              <p>
                IIT Jammu was established by the Government of India and is mentored by IIT Delhi.
                Situated at the Jagti campus, the institute has grown rapidly to become one of India's
                premier engineering institutions, offering cutting-edge programs across engineering,
                science, and humanities.
              </p>
              <p>
                The institute is located in the Union Territory of Jammu & Kashmir,
                serving as a beacon of technical education and research for the region.
              </p>
              <Link to="/about" className={styles.btnPrimary} style={{ marginTop: 20, display: 'inline-block' }}>
                Learn More
              </Link>
            </div>
            <div className={styles.aboutVisual}>
              <div className={styles.campusCard}>
                <div className={styles.campusImg} />
                <div className={styles.campusInfo}>
                  <strong>Jagti Campus</strong>
                  <span>Nagrota, Jammu — 181221</span>
                  <span>250+ Acres</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* News */}
      <section className={`${styles.news} section-pad`}>
        <div className="container">
          <div className={styles.sectionHead}>
            <span className="badge">Latest</span>
            <h2>News & Announcements</h2>
          </div>
          <div className={styles.newsList}>
            {NEWS.map(n => (
              <div key={n.title} className={styles.newsItem}>
                <span className={styles.newsDate}>{n.date}</span>
                <span className={styles.newsDot} />
                <span className={styles.newsTitle}>{n.title}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* AI CTA Banner */}
      <section className={styles.aiCta}>
        <div className="container">
          <div className={styles.aiCtaInner}>
            <div>
              <h2>Have questions about IIT Jammu?</h2>
              <p>Our AI assistant knows everything — fees, programs, faculty, admissions, and more.</p>
            </div>
            <button
              className={styles.btnGold}
              onClick={() => document.querySelector('[aria-label="Open AI Assistant"]')?.click()}
            >
              💬 Ask the AI Assistant
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
