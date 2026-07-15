import { useEffect, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import Reveal from '../components/Reveal'

// "Know your rights" across the languages AdhiKaar speaks. Rendered in Devanagari
// + romanized forms (the on-hand fonts are Noto Sans + Devanagari; romanized
// variants like Hinglish are a real product feature, so this is on-brand — no tofu).
const PHRASES = [
  { text: 'अपने अधिकार जानिए', lang: 'हिन्दी · Hindi', deva: true },
  { text: 'Apne adhikaar jaaniye', lang: 'Hinglish', deva: false },
  { text: 'Ungal urimaigalai ariyungal', lang: 'Tamil (Tanglish)', deva: false },
  { text: 'Mee hakkulanu telusukondi', lang: 'Telugu (Tenglish)', deva: false },
  { text: 'Nijer odhikar janun', lang: 'Bengali (Benglish)', deva: false },
  { text: 'Tumche adhikar jaana', lang: 'Marathi (Marlish)', deva: false },
  { text: 'Tamara hakko jaano', lang: 'Gujarati (Gujlish)', deva: false },
  { text: 'Nimma hakkugalannu tilidukolli', lang: 'Kannada (Kanglish)', deva: false },
  { text: 'Ningalude avakashangal ariyu', lang: 'Malayalam (Manglish)', deva: false },
  { text: 'Apne hakk jaano', lang: 'Punjabi (Punglish)', deva: false },
  { text: 'Know your rights', lang: 'English', deva: false },
]

const CHIPS = ['हिन्दी', 'Hinglish', 'தமிழ்', 'తెలుగు', 'বাংলা', 'मराठी', 'ગુજરાતી', 'ಕನ್ನಡ', 'മലയാളം', 'ਪੰਜਾਬੀ', 'English']

export default function Languages() {
  const reduce = useReducedMotion()
  const [i, setI] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setI((n) => (n + 1) % PHRASES.length), 1900)
    return () => clearInterval(t)
  }, [])
  const p = PHRASES[i]

  return (
    <section className="mx-auto max-w-5xl px-6 py-28 text-center">
      <Reveal>
        <p className="kicker mb-5">Eleven languages · zero literacy assumed</p>
      </Reveal>
      <Reveal delay={0.05}>
        <div className="flex min-h-[140px] flex-col items-center justify-center">
          <AnimatePresence mode="wait">
            <motion.h2
              key={p.text}
              initial={{ opacity: 0, y: reduce ? 0 : 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: reduce ? 0 : -16 }}
              transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] as const }}
              className={`text-4xl font-extrabold leading-tight text-bone sm:text-6xl ${p.deva ? 'deva' : ''}`}
            >
              {p.text}
            </motion.h2>
          </AnimatePresence>
          <div className="mt-3 h-5 text-sm uppercase tracking-[0.2em] text-indigo-bright">
            <AnimatePresence mode="wait">
              <motion.span
                key={p.lang}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                {p.lang}
              </motion.span>
            </AnimatePresence>
          </div>
        </div>
      </Reveal>

      <Reveal delay={0.1}>
        <p className="mx-auto mt-10 max-w-2xl text-lg text-bone-muted">
          Speak your problem, hear the answer back — including a fullscreen kiosk mode built for
          shared community devices.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-2.5">
          {CHIPS.map((c, idx) => (
            <span
              key={c}
              className={`rounded-full border px-3.5 py-1.5 text-sm transition-colors duration-300 ${
                idx === i
                  ? 'border-indigo-bright/60 bg-indigo/15 text-bone'
                  : 'border-bone/12 text-bone-muted'
              }`}
            >
              {c}
            </span>
          ))}
        </div>
      </Reveal>
    </section>
  )
}
