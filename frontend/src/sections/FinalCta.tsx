import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'

export default function FinalCta() {
  const reduce = useReducedMotion()
  return (
    <section className="relative flex min-h-[85vh] flex-col items-center justify-center overflow-hidden px-6 py-24 text-center">
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.16), transparent 62%)' }}
      />

      {/* the stamp */}
      <motion.div
        initial={reduce ? { opacity: 1, scale: 1, rotate: -4 } : { opacity: 0, scale: 2.4, rotate: 14 }}
        whileInView={{ opacity: 1, scale: 1, rotate: -4 }}
        viewport={{ once: true, margin: '-120px' }}
        transition={{ type: 'spring', stiffness: 220, damping: 15 }}
        className="relative mb-10 select-none rounded-lg border-4 border-turmeric px-8 py-3 text-3xl font-extrabold uppercase tracking-[0.12em] text-turmeric sm:text-5xl"
        style={{ textShadow: '0 0 30px rgba(245,158,11,0.3)' }}
      >
        Case Opened
      </motion.div>

      <motion.h2
        initial={{ opacity: 0, y: reduce ? 0 : 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.7, delay: 0.2 }}
        className="mb-8 max-w-3xl text-2xl font-bold leading-snug text-bone/90 sm:text-3xl"
      >
        A messy situation becomes a legal position you can explain in your own words.
      </motion.h2>

      <motion.a
        href="/app"
        initial={{ opacity: 0, y: reduce ? 0 : 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6, delay: 0.35 }}
        whileTap={reduce ? undefined : { scale: 0.96 }}
        className="group inline-flex items-center gap-3 rounded-t-xl rounded-b-sm bg-bone px-9 py-4 text-lg font-bold text-ink shadow-[0_18px_40px_-14px_rgba(99,102,241,0.6)] transition-transform duration-200 hover:-translate-y-0.5"
      >
        Start at the Clerk's Desk
        <ArrowRight className="h-5 w-5 transition-transform duration-200 group-hover:translate-x-1" />
      </motion.a>

      <p className="mt-14 max-w-xl text-sm leading-relaxed text-bone-muted/70">
        अधिKaar provides legal information, not legal advice. For complex matters, consult a
        qualified lawyer or call NALSA 15100 · Tele-Law 14454.
      </p>
      <p className="mt-6 text-xs uppercase tracking-[0.3em] text-bone-muted/50">
        <span className="deva">अधिकार जानो, अधिकार पाओ</span>
      </p>
    </section>
  )
}
