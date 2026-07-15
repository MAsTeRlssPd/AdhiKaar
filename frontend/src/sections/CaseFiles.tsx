import { motion, useReducedMotion } from 'framer-motion'
import { FileText, FileSignature, ShieldCheck } from 'lucide-react'
import Reveal from '../components/Reveal'

const CARDS = [
  {
    tab: 'Exhibit',
    icon: FileText,
    title: 'Documents & OCR',
    body: 'Photograph an FIR, a notice, a summons. It is read on-device and explained part by part — dates, sections, what to do next.',
    rot: -5,
  },
  {
    tab: 'Filing',
    icon: FileSignature,
    title: 'Drafts & deadlines',
    body: '45 guided templates — notices, RTI, complaints, bail. Drafts save to the case automatically; deadlines surface before they pass.',
    rot: 0,
  },
  {
    tab: 'Finding',
    icon: ShieldCheck,
    title: 'Verified analysis',
    body: 'One structured answer, checked claim by claim against the law, stress-tested from both sides, ending in a rights card you can share.',
    rot: 5,
  },
]

export default function CaseFiles() {
  const reduce = useReducedMotion()
  return (
    <section className="mx-auto max-w-6xl px-6 py-28 text-center">
      <Reveal>
        <p className="kicker mb-5">The dossier</p>
        <h2 className="mx-auto mb-4 max-w-3xl text-4xl font-extrabold leading-tight sm:text-6xl">
          One case file. Everything inside.
        </h2>
        <p className="mx-auto mb-16 max-w-2xl text-lg text-bone-muted">
          Not a chatbot with scattered tools. Open a case and the conversation, documents, drafts,
          deadlines, and analysis are already linked.
        </p>
      </Reveal>

      <div className="flex flex-col items-stretch justify-center gap-6 md:flex-row md:gap-5">
        {CARDS.map((c, idx) => (
          <motion.article
            key={c.title}
            initial={{ opacity: 0, y: reduce ? 0 : 40, rotate: reduce ? 0 : c.rot * 1.6 }}
            whileInView={{ opacity: 1, y: 0, rotate: reduce ? 0 : c.rot }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.6, delay: idx * 0.12, ease: [0.22, 1, 0.36, 1] as const }}
            whileHover={reduce ? undefined : { y: -8, rotate: 0, transition: { duration: 0.25 } }}
            className="relative flex-1 rounded-xl bg-bone px-7 pb-7 pt-10 text-left text-ink"
            style={{ boxShadow: 'var(--shadow-paper)' }}
          >
            <span className="absolute -top-3 left-6 rounded-t-md bg-turmeric px-3 py-1 text-[0.6rem] font-bold uppercase tracking-[0.14em] text-[#451A03]">
              {c.tab}
            </span>
            <c.icon className="mb-4 h-8 w-8 text-indigo-deep" />
            <h3 className="mb-2 text-xl font-bold">{c.title}</h3>
            <p className="text-[0.98rem] leading-relaxed text-ink/70">{c.body}</p>
          </motion.article>
        ))}
      </div>
    </section>
  )
}
