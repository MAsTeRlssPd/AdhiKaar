import { useEffect, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import Reveal from '../components/Reveal'

// Real mappings from AdhiKaar/data/ipc_bns_mapping.json — the codes actually changed.
const MAPPINGS = [
  { ipc: '420', bns: '318(4)', offence: 'Cheating' },
  { ipc: '302', bns: '103', offence: 'Murder' },
  { ipc: '379', bns: '303(2)', offence: 'Theft' },
  { ipc: '354', bns: '74', offence: 'Assault on a woman' },
  { ipc: '124A', bns: '152', offence: 'Sedition' },
]

const flip = {
  enter: { rotateX: -90, opacity: 0 },
  center: { rotateX: 0, opacity: 1 },
  exit: { rotateX: 90, opacity: 0 },
}

export default function Flipboard() {
  const reduce = useReducedMotion()
  const [i, setI] = useState(0)

  useEffect(() => {
    const ms = reduce ? 3200 : 2600
    const t = setInterval(() => setI((n) => (n + 1) % MAPPINGS.length), ms)
    return () => clearInterval(t)
  }, [reduce])

  const m = MAPPINGS[i]

  return (
    <section className="flex min-h-screen flex-col items-center justify-center px-6 py-24 text-center">
      <Reveal>
        <p className="kicker mb-5">Exhibit A · 1 July 2024</p>
        <h2 className="mx-auto mb-4 max-w-3xl text-4xl font-extrabold leading-tight sm:text-6xl">
          The law changed overnight.
        </h2>
        <p className="mx-auto mb-14 max-w-2xl text-lg text-bone-muted">
          India replaced the IPC and CrPC. Every old section number a citizen ever memorised became
          wrong. अधिKaar speaks both.
        </p>
      </Reveal>

      <Reveal delay={0.1}>
        <div
          className="relative flex items-center gap-6 rounded-2xl border border-bone/10 bg-ink-soft px-8 py-10 sm:gap-12 sm:px-16"
          style={{ boxShadow: 'var(--shadow-paper)', perspective: 800 }}
        >
          {/* OLD */}
          <div className="text-left">
            <div className="kicker mb-2">Old · IPC</div>
            <div className="relative h-[64px] w-[150px] sm:h-[84px] sm:w-[200px]">
              <AnimatePresence mode="popLayout">
                <motion.div
                  key={m.ipc}
                  variants={reduce ? undefined : flip}
                  initial={reduce ? { opacity: 0 } : 'enter'}
                  animate={reduce ? { opacity: 1 } : 'center'}
                  exit={reduce ? { opacity: 0 } : 'exit'}
                  transition={{ duration: 0.42, ease: 'easeInOut' }}
                  className="absolute inset-0 flex items-center font-extrabold tabular-nums text-bone-muted line-through decoration-turmeric/70 decoration-2"
                  style={{ fontSize: 'clamp(2.4rem,7vw,4.5rem)' }}
                >
                  {m.ipc}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>

          <ArrowRight className="h-8 w-8 shrink-0 text-indigo-bright sm:h-11 sm:w-11" />

          {/* NEW */}
          <div className="text-left">
            <div className="mb-2 text-[0.72rem] font-bold uppercase tracking-[0.28em] text-turmeric">New · BNS</div>
            <div className="relative h-[64px] w-[170px] sm:h-[84px] sm:w-[230px]">
              <AnimatePresence mode="popLayout">
                <motion.div
                  key={m.bns}
                  variants={reduce ? undefined : flip}
                  initial={reduce ? { opacity: 0 } : 'enter'}
                  animate={reduce ? { opacity: 1 } : 'center'}
                  exit={reduce ? { opacity: 0 } : 'exit'}
                  transition={{ duration: 0.42, ease: 'easeInOut' }}
                  className="absolute inset-0 flex items-center font-extrabold tabular-nums text-bone"
                  style={{ fontSize: 'clamp(2.4rem,7vw,4.5rem)', textShadow: '0 0 32px rgba(245,158,11,0.35)' }}
                >
                  {m.bns}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>
      </Reveal>

      <Reveal delay={0.15}>
        <div className="mt-8 h-6">
          <AnimatePresence mode="wait">
            <motion.p
              key={m.offence}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.3 }}
              className="text-lg text-bone-muted"
            >
              {m.offence}
            </motion.p>
          </AnimatePresence>
        </div>
        <p className="mt-10 text-sm font-semibold uppercase tracking-[0.18em] text-indigo-bright">
          216 IPC↔BNS · 80 CrPC↔BNSS mappings, built in
        </p>
      </Reveal>
    </section>
  )
}
