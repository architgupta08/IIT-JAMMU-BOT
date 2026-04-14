import React, { useState, useEffect } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import styles from './Header.module.css'

const NAV_LINKS = [
  { to: '/',           label: 'Home' },
  { to: '/about',      label: 'About' },
  { to: '/programs',   label: 'Programs' },
  { to: '/admissions', label: 'Admissions' },
  { to: '/faculty',    label: 'Faculty' },
  { to: '/research',   label: 'Research' },
  { to: '/campus',     label: 'Campus' },
  { to: '/placements', label: 'Placements' },
  { to: '/contact',    label: 'Contact' },
]

export default function Header() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 50)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => { setMenuOpen(false) }, [location])

  return (
    <header className={`${styles.header} ${scrolled ? styles.scrolled : ''}`}>
      {/* Top bar */}
      <div className={styles.topBar}>
        <div className={styles.topBarInner}>
          <span>Ministry of Education, Govt. of India</span>
          <div className={styles.topLinks}>
            <a href="https://www.iitjammu.ac.in" target="_blank" rel="noreferrer">
              Official Website ↗
            </a>
            <span className={styles.divider}>|</span>
            <span>📍 Jagti, Nagrota, Jammu — 181221</span>
          </div>
        </div>
      </div>

      {/* Main header */}
      <div className={styles.mainHeader}>
        <div className={styles.brand}>
          <div className={styles.logoBlock}>
            <svg width="52" height="52" viewBox="0 0 52 52" fill="none">
              <circle cx="26" cy="26" r="26" fill="#003366"/>
              <text x="26" y="18" textAnchor="middle" fill="#C5972A"
                fontFamily="Rajdhani,sans-serif" fontWeight="700" fontSize="9">IIT</text>
              <text x="26" y="30" textAnchor="middle" fill="#ffffff"
                fontFamily="Rajdhani,sans-serif" fontWeight="600" fontSize="7.5">JAMMU</text>
              <circle cx="26" cy="38" r="4" fill="#C5972A"/>
            </svg>
          </div>
          <Link to="/" className={styles.brandText}>
            <span className={styles.brandShort}>IIT Jammu</span>
            <span className={styles.brandFull}>
              Indian Institute of Technology Jammu
            </span>
            <span className={styles.brandTagline}>
              Established 2016 · Institute of National Importance
            </span>
          </Link>
        </div>

        {/* Demo badge */}
        <div className={styles.demoBadge}>
          <span>🤖</span>
          <span>AI Demo</span>
        </div>

        <button
          className={styles.menuToggle}
          onClick={() => setMenuOpen(v => !v)}
          aria-label="Toggle navigation"
        >
          <span className={menuOpen ? styles.close : styles.burger}>
            {menuOpen ? '✕' : '☰'}
          </span>
        </button>
      </div>

      {/* Navigation */}
      <nav className={`${styles.nav} ${menuOpen ? styles.navOpen : ''}`}>
        <div className={styles.navInner}>
          {NAV_LINKS.map(link => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              className={({ isActive }) =>
                `${styles.navLink} ${isActive ? styles.active : ''}`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </div>
      </nav>
    </header>
  )
}
