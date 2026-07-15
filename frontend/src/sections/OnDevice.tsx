import { motion, useReducedMotion } from 'framer-motion'
import { Mic, ScanText, Database, FileSignature } from 'lucide-react'
import Reveal from '../components/Reveal'

const CHAIN = [
  { icon: Mic, label: 'Voice', note: 'Speech in and out, Web Speech API' },
  { icon: ScanText, label: 'OCR', note: 'Tesseract.js reads documents in the browser' },
  { icon: Database, label: 'RAG', note: 'ChromaDB over 6,845 sections of law' },
  { icon: FileSignature, label: 'Draft', note: 'Gemma writes it, saved to localStorage' },
]

export default function OnDevice() {
  const reduce = useReducedMotion()
  return (
    <section className="mx-auto max-w-6xl px-6 py-28">
      <div className="grid items-center gap-14 lg:grid-cols-2">
        <Reveal>
          <p className="kicker mb-5">Chain of custody</p>
          <h2 className="mb-6 text-4xl font-extrabold leading-tight sm:text-5xl">
            Nothing leaves<br />this device.
          </h2>
          <p className="mb-4 text-lg leading-relaxed text-bone-muted">
            Gemma runs locally through Ollama. Retrieval, OCR, and every case file stay on the
            machine in front of you. There is no account, no telemetry, no server in the middle.
          </p>
          <p className="text-lg font-semibold text-bone">
            Pull the ethernet cable. It still works.
          </p>
        </Reveal>

        <div className="relative flex flex-col gap-4">
          {/* connecting line */}
          <div aria-hidden className="absolute left-[27px] top-8 bottom-8 w-px bg-gradient-to-b from-indigo/60 via-indigo/25 to-transparent" />
          {CHAIN.map((step, idx) => (
            <motion.div
              key={step.label}
              initial={{ opacity: 0, x: reduce ? 0 : 24 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.55, delay: idx * 0.12, ease: [0.22, 1, 0.36, 1] as const }}
              className="relative flex items-center gap-4 rounded-xl border border-bone/10 bg-bone px-5 py-4 text-ink"
              style={{ boxShadow: 'var(--shadow-paper)' }}
            >
              <div className="grid h-[54px] w-[54px] shrink-0 place-items-center rounded-lg bg-ink text-bone">
                <step.icon className="h-6 w-6" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-bold">{step.label}</div>
                <div className="text-sm text-ink/60">{step.note}</div>
              </div>
              <span className="shrink-0 rounded-md border border-turmeric/50 bg-turmeric/10 px-2 py-1 text-[0.62rem] font-bold uppercase tracking-[0.12em] text-turmeric-deep">
                On-device
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
