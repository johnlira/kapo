import { useQueryState } from 'nuqs'
import { SessionEntry } from '@/types/os'
import { Button } from '../../../ui/button'
import useSessionLoader from '@/hooks/useSessionLoader'
import { invalidateSessionRequest } from '@/hooks/useSessionLoader'
import { deleteSessionAPI } from '@/api/os'
import { useStore } from '@/store'
import { toast } from 'sonner'
import Icon from '@/components/ui/icon'
import { useState } from 'react'
import DeleteSessionModal from './DeleteSessionModal'
import useChatActions from '@/hooks/useChatActions'
import { cn } from '@/lib/utils'
import { sessionTimestamp } from '@/lib/session-time'

type SessionItemProps = SessionEntry & {
  isSelected: boolean
  currentSessionId: string | null
}
const SessionItem = ({
  session_name: title,
  session_id,
  created_at,
  updated_at,
  isSelected,
  currentSessionId
}: SessionItemProps) => {
  const [agentId] = useQueryState('agent')
  const [teamId] = useQueryState('team')
  const [dbId] = useQueryState('db_id')
  const [, setSessionId] = useQueryState('session')
  const { getSession } = useSessionLoader()
  const { selectedEndpoint, sessionsData, setSessionsData, mode } = useStore()
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const { clearChat } = useChatActions()
  const timestamp = sessionTimestamp(updated_at) || sessionTimestamp(created_at)
  const date = timestamp ? new Date(timestamp) : null
  const dateLabel =
    date && !Number.isNaN(date.getTime())
      ? new Intl.DateTimeFormat('pt-BR', {
          day: '2-digit',
          month: 'short'
        }).format(date)
      : null

  const handleGetSession = () => {
    if (!dbId || !(agentId || teamId) || useStore.getState().isStreaming) return

    invalidateSessionRequest()
    useStore.getState().setSelectedSessionId(session_id)
    useStore.getState().setMessages([])
    setSessionId(session_id)
    getSession(
      {
        entityType: mode,
        agentId,
        teamId,
        dbId
      },
      session_id
    )
  }

  const handleDeleteSession = async () => {
    if (!(agentId || teamId || dbId)) return
    setIsDeleting(true)
    try {
      const response = await deleteSessionAPI(
        selectedEndpoint,
        dbId ?? '',
        session_id
      )

      if (response?.ok && sessionsData) {
        setSessionsData(sessionsData.filter((s) => s.session_id !== session_id))
        // If the deleted session was the active one, clear the chat
        if (currentSessionId === session_id) {
          setSessionId(null)
          clearChat()
        }
        toast.success('Session deleted')
      } else {
        const errorMsg = await response?.text()
        toast.error(
          `Failed to delete session: ${response?.statusText || 'Unknown error'} ${errorMsg || ''}`
        )
      }
    } catch (error) {
      toast.error(
        `Failed to delete session: ${error instanceof Error ? error.message : String(error)}`
      )
    } finally {
      setIsDeleteModalOpen(false)
      setIsDeleting(false)
    }
  }
  return (
    <>
      <div
        role="button"
        tabIndex={0}
        aria-current={isSelected ? 'page' : undefined}
        className={cn(
          'group flex min-h-12 w-full items-center justify-between gap-2 rounded-xl border-l-2 px-3 py-2 transition-colors duration-200',
          isSelected
            ? 'border-brand bg-brand/10'
            : 'cursor-pointer border-transparent hover:bg-accent'
        )}
        onClick={handleGetSession}
        onKeyDown={(event) => {
          if (
            event.target === event.currentTarget &&
            (event.key === 'Enter' || event.key === ' ')
          ) {
            event.preventDefault()
            handleGetSession()
          }
        }}
      >
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <h4
            className={cn(
              'truncate text-sm font-medium text-secondary',
              isSelected && 'text-brand'
            )}
            title={title}
          >
            {title || 'Conversa sem título'}
          </h4>
          {dateLabel && <span className="text-xs text-muted">{dateLabel}</span>}
        </div>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Excluir conversa ${title || 'sem título'}`}
          className="size-7 shrink-0 text-muted opacity-0 transition-all duration-200 ease-in-out hover:text-destructive focus-visible:opacity-100 group-focus-within:opacity-100 group-hover:opacity-100 max-md:opacity-100"
          onClick={(e) => {
            e.stopPropagation()
            setIsDeleteModalOpen(true)
          }}
        >
          <Icon type="trash" size="xs" />
        </Button>
      </div>
      <DeleteSessionModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onDelete={handleDeleteSession}
        isDeleting={isDeleting}
      />
    </>
  )
}

export default SessionItem
