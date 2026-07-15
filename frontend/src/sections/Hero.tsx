import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, ShieldCheck, WifiOff } from 'lucide-react'

const line = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07, delayChildren: 0.15 } },
}
const word = {
  hidden: { opacity: 0, y: 28 },
  show: { opacity: 1, y: 0, transition: { duration: 0.7, ease: [0.22, 1, 0.36, 1] as const } },
}

export default function Hero() {
  const reduce = useReducedMotion()
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center px-6 text-center">
      {/* the lamp */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-[38%] -z-0 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.22), transparent 62%)', filter: 'blur(20px)' }}
      />

      <motion.div
        initial={reduce ? { opacity: 1 } : { opacity: 0, scale: 0.6, rotate: -8 }}
        animate={{ opacity: 1, scale: 1, rotate: -3 }}
        transition={{ type: 'spring', stiffness: 260, damping: 16, delay: 0.1 }}
        className="mb-8 inline-flex items-center gap-2 rounded-full border border-turmeric/40 bg-turmeric/10 px-4 py-1.5 text-[0.7rem] font-bold uppercase tracking-[0.16em] text-turmeric"
      >
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-turmeric" />
        Kaggle · Build with Gemma · Track 1
      </motion.div>

      <motion.div variants={line} initial="hidden" animate="show" className="max-w-4xl">
        <motion.h1 variants={word} className="mb-6 text-6xl font-extrabold leading-[0.95] sm:text-8xl">
          <span className="deva">अधि</span>Kaar
        </motion.h1>

        <div className="mb-7 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-2xl font-bold text-bone/85 sm:text-4xl">
          <motion.span variants={word}>Your rights.</motion.span>
          <motion.span variants={word}>Your language.</motion.span>
          <motion.span variants={word} className="text-indigo-bright">Your device.</motion.span>
        </div>

        <motion.p variants={word} className="mx-auto mb-10 max-w-2xl text-lg leading-relaxed text-bone-muted">
          A legal assistant for every Indian citizen, built on Gemma.
          <span className="text-bone"> 6,845 sections of Indian law</span>, running entirely on your
          machine. No signup. No cloud. Nothing leaves the room.
        </motion.p>

        <motion.div variants={word} className="flex flex-col items-center gap-5">
          <a
            href="/app"
            className="group relative inline-flex items-center gap-3 rounded-t-xl rounded-b-sm bg-bone px-8 py-4 text-lg font-bold text-ink shadow-[0_18px_40px_-14px_rgba(99,102,241,0.6)] transition-transform duration-200 hover:-translate-y-0.5 active:translate-y-0"
          >
            <span
              aria-hidden
              className="absolute -top-2 left-5 h-2 w-16 rounded-t-md bg-bone"
            />
            Open a Case
            <ArrowRight className="h-5 w-5 transition-transform duration-200 group-hover:translate-x-1" />
          </a>
          <div className="flex items-center gap-6 text-sm text-bone-muted">
            <span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-4 w-4 text-indigo" /> 100% on-device</span>
            <span className="inline-flex items-center gap-1.5"><WifiOff className="h-4 w-4 text-indigo" /> Works offline</span>
          </div>
        </motion.div>
      </motion.div>

      {/* scroll hint */}
      <motion.div
        aria-hidden
        initial={{ opacity: 0 }}
        animate={{ opacity: reduce ? 0 : 0.5 }}
        transition={{ delay: 1.4, duration: 1 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2 text-xs uppercase tracking-[0.3em] text-bone-muted"
      >
        <motion.span
          animate={reduce ? {} : { y: [0, 6, 0] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="inline-block"
        >
          scroll
        </motion.span>
      </motion.div>
    </section>
  )
}
