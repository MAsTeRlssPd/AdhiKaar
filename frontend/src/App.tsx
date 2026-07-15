import { useEffect } from 'react'
import Lenis from 'lenis'
import { useReducedMotion } from 'framer-motion'
import Hero from './sections/Hero'
import Flipboard from './sections/Flipboard'
import OnDevice from './sections/OnDevice'
import CaseFiles from './sections/CaseFiles'
import Languages from './sections/Languages'
import FinalCta from './sections/FinalCta'

export default function App() {
  const reduce = useReducedMotion()

  useEffect(() => {
    if (reduce) return // no smooth-scroll hijack when the user asked for calm
    const lenis = new Lenis({ duration: 1.1, smoothWheel: true })
    let id = 0
    const raf = (t: number) => {
      lenis.raf(t)
      id = requestAnimationFrame(raf)
    }
    id = requestAnimationFrame(raf)
    return () => {
      cancelAnimationFrame(id)
      lenis.destroy()
    }
  }, [reduce])

  return (
    <main className="relative">
      {/* fixed vignette so the whole page reads as one dim room */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          background:
            'radial-gradient(120% 80% at 50% -10%, rgba(99,102,241,0.10), transparent 55%), radial-gradient(100% 100% at 50% 120%, rgba(0,0,0,0.6), transparent 60%)',
        }}
      />
      <div className="relative z-10">
        <Hero />
        <Flipboard />
        <OnDevice />
        <CaseFiles />
        <Languages />
        <FinalCta />
      </div>
    </main>
  )
}
