import React from 'react'
import styles from './InfoPage.module.css'
export default function Research() {
  return (
    <div className={styles.page}>
      <div className={styles.pageHero} style={{ background:'linear-gradient(135deg,#0d3349,#1a6fc4)' }}>
        <div className="container"><span className="badge">Research</span><h1>Research & Innovation</h1><p>Pushing boundaries through cutting-edge research</p></div>
      </div>
      <div className="container section-pad">
        <div className={styles.infoGrid}>
          <div className={styles.card}><h3>🖥️ HPC Facilities</h3><p><strong>Agastya Cluster:</strong> 1608 CPU cores, 66 NVIDIA Tesla V100 GPUs — among India's top 50 HPC systems.</p><p style={{marginTop:8}}><strong>Saptarshi Cluster:</strong> Additional computational infrastructure for research.</p></div>
          <div className={styles.card}><h3>🔬 Central Instruments</h3><ul><li>X-Ray Diffractometer (XRD)</li><li>Scanning Electron Microscope (SEM)</li><li>Transmission Electron Microscope (TEM)</li><li>NMR Spectrometer</li><li>FTIR, UV-Vis Spectrophotometer</li></ul></div>
          <div className={styles.card}><h3>📚 Research Stats</h3><ul><li>500+ publications (2022–24)</li><li>₹50+ Crore sponsored research</li><li>12+ active patents</li><li>Industry partnerships: TCS, DRDO, DST</li><li>20+ ongoing PhD scholars</li></ul></div>
          <div className={styles.card}><h3>🏭 Research Centers</h3><ul><li>Center for Artificial Intelligence</li><li>Center for Electric Vehicles</li><li>Center for Sustainable Energy</li><li>VLSI Design Lab</li><li>Smart Structures Lab</li></ul></div>
          <div className={styles.card}><h3>💼 Funded Projects</h3><ul><li>DST, SERB, CSIR funded</li><li>Ministry of Education grants</li><li>Industry-sponsored R&D</li><li>International collaborations (USA, EU, Japan)</li></ul></div>
          <div className={styles.card}><h3>🎯 PhD Fellowships</h3><ul><li>PMRF: ₹70,000–80,000/month</li><li>Institute Fellowship: ₹31,000/month</li><li>UGC/CSIR-JRF: As per norms</li><li>Visvesvaraya Fellowship (IT-related)</li></ul></div>
        </div>
        <div className={styles.aiPrompt} style={{marginTop:28}}>
          <span>🤖</span><span>Ask the AI about specific labs, funded projects, or Ph.D openings at IIT Jammu!</span>
        </div>
      </div>
    </div>
  )
}
