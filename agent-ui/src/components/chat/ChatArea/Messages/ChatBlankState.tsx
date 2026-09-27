'use client'

import { motion } from 'framer-motion'
import Icon from '@/components/ui/icon'
const ChatBlankState = ({ userName }: { userName?: string | null }) => {
  const firstName = userName?.trim().split(/\s+/)[0]
  return (
    <section
      className="flex flex-col items-center text-center font-geist"
      aria-label="Welcome message"
    >
      <div className="flex max-w-3xl flex-col gap-y-8">
        <motion.h1
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="text-3xl font-[600] tracking-tight"
        >
          <div className="flex flex-wrap items-center justify-center gap-x-2 font-medium">
            <span className="flex items-center font-[600]">
              Olá, {firstName || 'bem-vindo'}! Eu sou o
            </span>
            <span className="inline-flex -rotate-3 items-center gap-2 rounded-lg bg-primary px-3 py-1 text-xl font-semibold tracking-tight text-background transition-transform duration-200 hover:rotate-0">
              <Icon type="agno" size="xs" className="text-background" />
              Kapo
            </span>
            <span className="font-normal">
              seu assistente para tirar dúvidas sobre o QuarkClinic.
            </span>
          </div>
        </motion.h1>
      </div>
    </section>
  )
}

export default ChatBlankState
