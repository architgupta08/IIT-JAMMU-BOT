import React, { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Header from './components/layout/Header.jsx'
import Footer from './components/layout/Footer.jsx'
import ChatBot from './components/chatbot/ChatBot.jsx'
import './index.css'

// Lazy-loaded pages
const Home       = lazy(() => import('./pages/Home.jsx'))
const About      = lazy(() => import('./pages/About.jsx'))
const Programs   = lazy(() => import('./pages/Programs.jsx'))
const Admissions = lazy(() => import('./pages/Admissions.jsx'))
const Faculty    = lazy(() => import('./pages/Faculty.jsx'))
const Research   = lazy(() => import('./pages/Research.jsx'))
const Campus     = lazy(() => import('./pages/Campus.jsx'))
const Placements = lazy(() => import('./pages/Placements.jsx'))
const Contact    = lazy(() => import('./pages/Contact.jsx'))
const NotFound   = lazy(() => import('./pages/NotFound.jsx'))

const PageLoader = () => (
  <div style={{
    display: 'flex', justifyContent: 'center',
    alignItems: 'center', height: '60vh',
    flexDirection: 'column', gap: 16
  }}>
    <div style={{
      width: 40, height: 40, borderRadius: '50%',
      border: '3px solid #e2e8f0',
      borderTopColor: '#003366',
      animation: 'spin 0.8s linear infinite'
    }} />
    <span style={{ color: '#64748b', fontFamily: 'Rajdhani, sans-serif', fontSize: 14 }}>
      Loading...
    </span>
  </div>
)

export default function App() {
  return (
    <BrowserRouter>
      <Header />
      <main>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/"            element={<Home />} />
            <Route path="/about"       element={<About />} />
            <Route path="/programs"    element={<Programs />} />
            <Route path="/admissions"  element={<Admissions />} />
            <Route path="/faculty"     element={<Faculty />} />
            <Route path="/research"    element={<Research />} />
            <Route path="/campus"      element={<Campus />} />
            <Route path="/placements"  element={<Placements />} />
            <Route path="/contact"     element={<Contact />} />
            <Route path="*"            element={<NotFound />} />
          </Routes>
        </Suspense>
      </main>
      <Footer />
      {/* Floating AI Chatbot — appears on every page */}
      <ChatBot />
    </BrowserRouter>
  )
}
