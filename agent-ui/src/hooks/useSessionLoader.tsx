import { useCallback } from 'react'
import { getSessionAPI, getAllSessionsAPI } from '@/api/os'
import { useStore } from '../store'
import { toast } from 'sonner'
import { ChatMessage, ToolCall, ReasoningMessage, ChatEntry } from '@/types/os'
import { getJsonMarkdown } from '@/lib/utils'

const SCOPE_REPLY =
  'Só posso orientar sobre funcionalidades e regras de negócio do QuarkClinic.'

// Session rows own separate hook instances; the store keeps the current
// selection so an older request cannot overwrite a newer chat.
let activeSessionRequest = 0
let activeSessionsRequest = 0

export const invalidateSessionRequest = () => ++activeSessionRequest
export const invalidateSessionsRequest = () => ++activeSessionsRequest

interface LoaderArgs {
  entityType: 'agent' | 'team' | null
  agentId?: string | null
  teamId?: string | null
  dbId: string | null
}

const useSessionLoader = () => {
  const setMessages = useStore((state) => state.setMessages)
  const selectedEndpoint = useStore((state) => state.selectedEndpoint)
  const setIsSessionsLoading = useStore((state) => state.setIsSessionsLoading)
  const setSessionsData = useStore((state) => state.setSessionsData)

  const getSessions = useCallback(
    async ({ entityType, agentId, teamId, dbId }: LoaderArgs) => {
      const request = invalidateSessionsRequest()
      const selectedId = entityType === 'agent' ? agentId : teamId
      if (!selectedEndpoint || !entityType || !selectedId || !dbId) {
        setIsSessionsLoading(false)
        return
      }

      try {
        setIsSessionsLoading(true)

        const sessions = await getAllSessionsAPI(
          selectedEndpoint,
          entityType,
          selectedId,
          dbId
        )
        if (request === activeSessionsRequest) {
          setSessionsData(sessions.data ?? [])
        }
      } catch {
        if (request === activeSessionsRequest) {
          toast.error('Error loading sessions')
          setSessionsData([])
        }
      } finally {
        if (request === activeSessionsRequest) setIsSessionsLoading(false)
      }
    },
    [selectedEndpoint, setSessionsData, setIsSessionsLoading]
  )

  const getSession = useCallback(
    async (
      { entityType, agentId, teamId, dbId }: LoaderArgs,
      sessionId: string
    ) => {
      const request = invalidateSessionRequest()
      const selectedId = entityType === 'agent' ? agentId : teamId
      if (
        !selectedEndpoint ||
        !sessionId ||
        !entityType ||
        !selectedId ||
        !dbId
      )
        return

      try {
        const response: ChatEntry[] | null = await getSessionAPI(
          selectedEndpoint,
          entityType,
          sessionId,
          dbId
        )
        if (
          request !== activeSessionRequest ||
          useStore.getState().selectedSessionId !== sessionId ||
          useStore.getState().isStreaming
        )
          return null
        if (response) {
          if (Array.isArray(response)) {
            const messagesFor = response.flatMap((run) => {
              const filteredMessages: ChatMessage[] = []

              if (run) {
                const input = run.run_input ?? run.input?.input_content
                filteredMessages.push({
                  role: 'user',
                  content: typeof input === 'string' ? input : '',
                  created_at: run.created_at
                })
              }

              if (run) {
                const offTopic =
                  run.status === 'ERROR' &&
                  run.events?.some(
                    (event) =>
                      event.event === 'RunError' &&
                      event.error_id === 'off_topic'
                  )
                const toolCalls = [
                  ...(run.tools ?? []),
                  ...(run.extra_data?.reasoning_messages ?? []).reduce(
                    (acc: ToolCall[], msg: ReasoningMessage) => {
                      if (msg.role === 'tool') {
                        acc.push({
                          role: msg.role,
                          content: msg.content,
                          tool_call_id: msg.tool_call_id ?? '',
                          tool_name: msg.tool_name ?? '',
                          tool_args: msg.tool_args ?? {},
                          tool_call_error: msg.tool_call_error ?? false,
                          metrics: msg.metrics ?? { time: 0 },
                          created_at:
                            msg.created_at ?? Math.floor(Date.now() / 1000)
                        })
                      }
                      return acc
                    },
                    []
                  )
                ]

                filteredMessages.push({
                  role: 'agent',
                  content: offTopic
                    ? SCOPE_REPLY
                    : ((run.content as string) ?? ''),
                  tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
                  extra_data: run.extra_data,
                  images: run.images,
                  videos: run.videos,
                  audio: run.audio,
                  response_audio: run.response_audio,
                  created_at: run.created_at
                })
              }
              return filteredMessages
            })

            const processedMessages = messagesFor.map(
              (message: ChatMessage) => {
                if (Array.isArray(message.content)) {
                  const textContent = message.content
                    .filter((item: { type: string }) => item.type === 'text')
                    .map((item) => item.text)
                    .join(' ')

                  return {
                    ...message,
                    content: textContent
                  }
                }
                if (typeof message.content !== 'string') {
                  return {
                    ...message,
                    content: getJsonMarkdown(message.content)
                  }
                }
                return message
              }
            )

            if (
              request !== activeSessionRequest ||
              useStore.getState().selectedSessionId !== sessionId ||
              useStore.getState().isStreaming
            )
              return null
            setMessages(processedMessages)
            return processedMessages
          }
        }
      } catch {
        return null
      }
    },
    [selectedEndpoint, setMessages]
  )

  return { getSession, getSessions }
}

export default useSessionLoader
