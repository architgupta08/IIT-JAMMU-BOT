import React from 'react'
import styles from './InfoPage.module.css'
export default function Campus() {
  return (
    <div className={styles.page}>
      <div className={styles.pageHero} style={{ background:'linear-gradient(135deg,#1b4332,#2d6a4f)' }}>
        <div className="container"><span className="badge">Campus Life</span><h1>Campus & Facilities</h1><p>A vibrant, modern campus in the foothills of the Shivaliks</p></div>
      </div>
      <div className="container section-pad">
        <div className={styles.infoGrid}>
          <div className={styles.card}><h3>🏠 Hostels</h3><ul><li>9 Boys' hostels + 2 Girls' hostels</li><li>Double/Single occupancy rooms</li><li>Charges: ₹41,320–60,230/year</li><li>24/7 Wi-Fi (1 Gbps campus network)</li><li>Common rooms, TV lounge</li></ul></div>
          <div className={styles.card}><h3>🍽️ Mess & Dining</h3><ul><li>Central Mess — veg & non-veg</li><li>Multiple canteens & cafeterias</li><li>Night canteen available</li><li>Mess charges: ~₹3,200–3,500/month</li></ul></div>
          <div className={styles.card}><h3>📚 Library</h3><ul><li>Central library — 40,000+ books</li><li>E-journals: IEEE, Elsevier, Springer</li><li>24×7 reading room</li><li>Digital library access</li></ul></div>
          <div className={styles.card}><h3>⚽ Sports</h3><ul><li>Cricket ground</li><li>Football, volleyball, basketball courts</li><li>Badminton, table tennis halls</li><li>Gymnasium</li><li>Swimming pool (under development)</li></ul></div>
          <div className={styles.card}><h3>🏥 Medical</h3><ul><li>On-campus medical centre</li><li>Qualified medical officer</li><li>Emergency ambulance</li><li>Empanelled hospitals in Jammu</li></ul></div>
          <div className={styles.card}><h3>📍 Location</h3><ul><li>Jagti campus, Nagrota, Jammu</li><li>18 km from Jammu city centre</li><li>RSRDC bus connectivity</li><li>Nearest airport: Jammu Airport (~20 km)</li><li>GPS: 32.7685°N, 74.8571°E</li></ul></div>
        </div>
        <div className={styles.aiPrompt} style={{marginTop:28}}>
          <span>🤖</span><span>Ask the AI about hostel allocation, mess menu, sports facilities, or how to reach campus!</span>
        </div>
      </div>
    </div>
  )
}
