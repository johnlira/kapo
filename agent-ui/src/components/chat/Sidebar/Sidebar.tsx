'use client'
import { Button } from '@/components/ui/button'
import useChatActions from '@/hooks/useChatActions'
import { useStore } from '@/store'
import { motion } from 'framer-motion'
import { useState, useEffect } from 'react'
import Icon from '@/components/ui/icon'
import Sessions from './Sessions'

const SidebarHeader = () => (
  <div className="flex items-center gap-1.5">
    <Icon type="agno" size="sm" />
    <span className="text-lg font-semibold tracking-tight text-primary">
      Kapo
    </span>
  </div>
)

const NewChatButton = ({
  disabled,
  onClick
}: {
  disabled: boolean
  onClick: () => void
}) => (
  <Button
    onClick={onClick}
    disabled={disabled}
    size="lg"
    className="h-9 w-full justify-start gap-2 rounded-xl bg-brand px-3 text-sm font-semibold text-white hover:bg-brand/90 disabled:bg-brand/60 disabled:text-white/80"
  >
    <Icon type="plus-icon" size="xs" className="text-white" />
    <span>Nova conversa</span>
  </Button>
)

const AgentStatus = () => {
  const { isEndpointActive, isEndpointLoading } = useStore()
  const { initialize } = useChatActions()
  const [isRotating, setIsRotating] = useState(false)

  const status = isEndpointLoading
    ? 'Verificando...'
    : isEndpointActive
      ? 'Ativo'
      : 'Indisponível'

  const handleRefresh = async () => {
    setIsRotating(true)
    await initialize()
    setTimeout(() => setIsRotating(false), 500)
  }

  return (
    <div className="flex flex-col items-start gap-2">
      <div className="text-xs font-semibold text-muted">Status do agente</div>
      <div className="flex w-full items-center gap-1">
        <div
          role="status"
          className="flex h-9 w-full items-center justify-between rounded-xl border border-border bg-background px-3 text-xs font-medium text-secondary"
        >
          <span>{status}</span>
          <div
            className={`size-2 shrink-0 rounded-full ${isEndpointLoading ? 'bg-muted' : isEndpointActive ? 'bg-positive' : 'bg-destructive'}`}
          />
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleRefresh}
          aria-label="Atualizar status do agente"
          className="shrink-0 text-muted hover:bg-accent hover:text-primary"
        >
          <motion.div
            key={isRotating ? 'rotating' : 'idle'}
            animate={{ rotate: isRotating ? 360 : 0 }}
            transition={{ duration: 0.5, ease: 'easeInOut' }}
          >
            <Icon type="refresh" size="xs" />
          </motion.div>
        </Button>
      </div>
    </div>
  )
}

const Sidebar = () => {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const { clearChat, focusChatInput, initialize } = useChatActions()
  const { messages, selectedEndpoint, hydrated, mode } = useStore()
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
    if (!hydrated) useStore.getState().setHydrated()
    else initialize()
  }, [selectedEndpoint, initialize, hydrated, mode])

  const handleNewChat = () => {
    clearChat()
    focusChatInput()
  }

  return (
    <motion.aside
      className="relative flex h-screen shrink-0 grow-0 flex-col overflow-hidden border-r border-border bg-primaryAccent px-3 py-5 font-geist"
      initial={{ width: '18rem' }}
      animate={{ width: isCollapsed ? '3.5rem' : '18rem' }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
    >
      <motion.button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="absolute right-3 top-6 z-10 rounded-lg p-1 text-primary hover:bg-accent"
        aria-label={
          isCollapsed ? 'Expandir barra lateral' : 'Recolher barra lateral'
        }
        type="button"
        whileTap={{ scale: 0.95 }}
      >
        <Icon
          type="sheet"
          size="xs"
          className={`transform ${isCollapsed ? 'rotate-180' : 'rotate-0'}`}
        />
      </motion.button>
      <motion.div
        className="flex h-full min-h-0 w-[16.5rem] flex-col"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: isCollapsed ? 0 : 1, x: isCollapsed ? -20 : 0 }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
        style={{
          pointerEvents: isCollapsed ? 'none' : 'auto'
        }}
      >
        <SidebarHeader />
        <div className="mt-7 flex min-h-0 flex-1 flex-col gap-5">
          <NewChatButton
            disabled={messages.length === 0}
            onClick={handleNewChat}
          />
          {isMounted && <Sessions />}
        </div>
        {isMounted && (
          <div className="mt-4 shrink-0 border-t border-border pt-4">
            <AgentStatus />
          </div>
        )}
      </motion.div>
    </motion.aside>
  )
}

export default Sidebar
