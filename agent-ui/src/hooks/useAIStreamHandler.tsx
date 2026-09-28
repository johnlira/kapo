import { useCallback } from 'react'

import { APIRoutes } from '@/api/routes'

import useChatActions from '@/hooks/useChatActions'
import { useStore } from '../store'
import { RunEvent, RunResponseContent, type RunResponse } from '@/types/os'
import useAIResponseStream from './useAIResponseStream'
import { ToolCall } from '@/types/os'
import { useQueryState } from 'nuqs'
import { invalidateSessionRequest } from './useSessionLoader'

const extractReadableContent = (content: object): string | undefined => {
  const record = content as Record<string, unknown>
  for (const key of ['answer', 'response', 'text', 'message', 'content']) {
    if (typeof record[key] === 'string') return record[key]
  }
  return undefined
}

const useAIChatStreamHandler = () => {
  const setMessages = useStore((state) => state.setMessages)
  const { addMessage, focusChatInput } = useChatActions()
  const [agentId] = useQueryState('agent')
  const [teamId] = useQueryState('team')
  const [sessionId, setSessionId] = useQueryState('session')
  const selectedEndpoint = useStore((state) => state.selectedEndpoint)
  const mode = useStore((state) => state.mode)
  const setStreamingErrorMessage = useStore(
    (state) => state.setStreamingErrorMessage
  )
  const setIsStreaming = useStore((state) => state.setIsStreaming)
  const setSessionsData = useStore((state) => state.setSessionsData)
  const { streamResponse } = useAIResponseStream()

  const updateMessagesWithErrorState = useCallback(() => {
    setMessages((prevMessages) => {
      const newMessages = [...prevMessages]
      const lastMessage = newMessages[newMessages.length - 1]
      if (lastMessage && lastMessage.role === 'agent') {
        newMessages[newMessages.length - 1] = {
          ...lastMessage,
          streamingError: true,
          active_tool_name: null
        }
      }
      return newMessages
    })
  }, [setMessages])

  /**
   * Processes a new tool call and adds it to the message
   * @param toolCall - The tool call to add
   * @param prevToolCalls - The previous tool calls array
   * @returns Updated tool calls array
   */
  const processToolCall = useCallback(
    (toolCall: ToolCall, prevToolCalls: ToolCall[] = []) => {
      const toolCallId =
        toolCall.tool_call_id || `${toolCall.tool_name}-${toolCall.created_at}`

      const existingToolCallIndex = prevToolCalls.findIndex(
        (tc) =>
          (tc.tool_call_id && tc.tool_call_id === toolCall.tool_call_id) ||
          (!tc.tool_call_id &&
            toolCall.tool_name &&
            toolCall.created_at &&
            `${tc.tool_name}-${tc.created_at}` === toolCallId)
      )
      if (existingToolCallIndex >= 0) {
        const updatedToolCalls = [...prevToolCalls]
        updatedToolCalls[existingToolCallIndex] = {
          ...updatedToolCalls[existingToolCallIndex],
          ...toolCall
        }
        return updatedToolCalls
      } else {
        return [...prevToolCalls, toolCall]
      }
    },
    []
  )

  /**
   * Processes tool calls from a chunk, handling both single tool object and tools array formats
   * @param chunk - The chunk containing tool call data
   * @param existingToolCalls - The existing tool calls array
   * @returns Updated tool calls array
   */
  const processChunkToolCalls = useCallback(
    (
      chunk: RunResponseContent | RunResponse,
      existingToolCalls: ToolCall[] = []
    ) => {
      let updatedToolCalls = [...existingToolCalls]
      // Handle new single tool object format
      if (chunk.tool) {
        updatedToolCalls = processToolCall(chunk.tool, updatedToolCalls)
      }
      // Handle legacy tools array format
      if (chunk.tools && chunk.tools.length > 0) {
        for (const toolCall of chunk.tools) {
          updatedToolCalls = processToolCall(toolCall, updatedToolCalls)
        }
      }

      return updatedToolCalls
    },
    [processToolCall]
  )

  const handleStreamResponse = useCallback(
    async (input: string | FormData) => {
      const startedAt = Date.now()
      const selectedSessionId = sessionId
      let assignedSessionId: string | null = null
      const isCurrentChat = () =>
        useStore.getState().selectedSessionId ===
        (assignedSessionId ?? selectedSessionId)
      const current = useStore.getState()
      if (current.selectedSessionId !== selectedSessionId) {
        current.setSelectedSessionId(selectedSessionId)
        current.setMessages([])
      }
      setStreamingErrorMessage('')
      invalidateSessionRequest()
      setIsStreaming(true)

      const formData = input instanceof FormData ? input : new FormData()
      if (typeof input === 'string') {
        formData.append('message', input)
      }

      setMessages((prevMessages) => {
        if (prevMessages.length >= 2) {
          const lastMessage = prevMessages[prevMessages.length - 1]
          const secondLastMessage = prevMessages[prevMessages.length - 2]
          if (
            lastMessage.role === 'agent' &&
            lastMessage.streamingError &&
            secondLastMessage.role === 'user'
          ) {
            return prevMessages.slice(0, -2)
          }
        }
        return prevMessages
      })

      addMessage({
        role: 'user',
        content: formData.get('message') as string,
        created_at: Math.floor(Date.now() / 1000)
      })

      addMessage({
        role: 'agent',
        content: '',
        tool_calls: [],
        active_tool_name: null,
        streamingError: false,
        started_at: startedAt,
        created_at: Math.floor(Date.now() / 1000) + 1
      })

      let lastContent = ''
      try {
        const endpointUrl = selectedEndpoint

        let RunUrl: string | null = null

        if (mode === 'team' && teamId) {
          RunUrl = APIRoutes.TeamRun(endpointUrl, teamId)
        } else if (mode === 'agent' && agentId) {
          RunUrl = APIRoutes.AgentRun(endpointUrl).replace(
            '{agent_id}',
            agentId
          )
        }

        if (!RunUrl) {
          updateMessagesWithErrorState()
          setStreamingErrorMessage('Please select an agent or team first.')
          setIsStreaming(false)
          return
        }

        formData.append('stream', 'true')
        formData.append('session_id', sessionId ?? '')

        await streamResponse({
          apiUrl: RunUrl,
          requestBody: formData,
          onChunk: (chunk: RunResponse) => {
            if (!isCurrentChat()) return
            if (chunk.session_id && !selectedSessionId && !assignedSessionId) {
              assignedSessionId = chunk.session_id
              useStore.getState().setSelectedSessionId(chunk.session_id)
              setSessionId(chunk.session_id)
            }
            if (
              chunk.event === RunEvent.RunStarted ||
              chunk.event === RunEvent.TeamRunStarted
            ) {
              if (chunk.session_id) setSessionId(chunk.session_id)
              if (
                (!sessionId || sessionId !== chunk.session_id) &&
                chunk.session_id
              ) {
                const sessionData = {
                  session_id: chunk.session_id as string,
                  session_name: formData.get('message') as string,
                  created_at: chunk.created_at
                }
                setSessionsData((prevSessionsData) => {
                  const sessionExists = prevSessionsData?.some(
                    (session) => session.session_id === chunk.session_id
                  )
                  if (sessionExists) {
                    return prevSessionsData
                  }
                  return [sessionData, ...(prevSessionsData ?? [])]
                })
              }
            } else if (
              chunk.event === RunEvent.ToolCallStarted ||
              chunk.event === RunEvent.TeamToolCallStarted ||
              chunk.event === RunEvent.ToolCallCompleted ||
              chunk.event === RunEvent.TeamToolCallCompleted
            ) {
              setMessages((prevMessages) => {
                const newMessages = [...prevMessages]
                const lastMessage = newMessages[newMessages.length - 1]
                if (lastMessage && lastMessage.role === 'agent') {
                  const updatedMessage = { ...lastMessage }
                  const toolCalls = processChunkToolCalls(
                    chunk,
                    lastMessage.tool_calls
                  )
                  const isToolStart =
                    chunk.event === RunEvent.ToolCallStarted ||
                    chunk.event === RunEvent.TeamToolCallStarted
                  const incomingTool = chunk.tool ?? chunk.tools?.at(-1)
                  updatedMessage.tool_calls = toolCalls
                  if (isToolStart) {
                    updatedMessage.active_tool_name =
                      incomingTool?.tool_name ?? lastMessage.active_tool_name
                  } else if (
                    !incomingTool?.tool_call_id ||
                    toolCalls.findLast(
                      (toolCall) =>
                        toolCall.tool_name === lastMessage.active_tool_name
                    )?.tool_call_id === incomingTool.tool_call_id
                  ) {
                    updatedMessage.active_tool_name = null
                  }
                  newMessages[newMessages.length - 1] = updatedMessage
                }
                return newMessages
              })
            } else if (
              chunk.event === RunEvent.RunContent ||
              chunk.event === RunEvent.TeamRunContent
            ) {
              setMessages((prevMessages) => {
                const newMessages = [...prevMessages]
                const lastMessage = newMessages[newMessages.length - 1]
                if (!lastMessage || lastMessage.role !== 'agent')
                  return newMessages
                const updatedMessage = { ...lastMessage }
                if (typeof chunk.content === 'string') {
                  const uniqueContent = chunk.content.startsWith(lastContent)
                    ? chunk.content.slice(lastContent.length)
                    : chunk.content
                  updatedMessage.content += uniqueContent
                  lastContent = chunk.content

                  // Handle tool calls streaming
                  updatedMessage.tool_calls = processChunkToolCalls(
                    chunk,
                    lastMessage.tool_calls
                  )
                  if (updatedMessage.thinking_seconds === undefined) {
                    updatedMessage.thinking_seconds = Math.max(
                      0,
                      Math.floor((Date.now() - startedAt) / 1000)
                    )
                  }
                  if (chunk.extra_data?.reasoning_steps) {
                    updatedMessage.extra_data = {
                      ...updatedMessage.extra_data,
                      reasoning_steps: chunk.extra_data.reasoning_steps
                    }
                  }

                  if (chunk.extra_data?.references) {
                    updatedMessage.extra_data = {
                      ...updatedMessage.extra_data,
                      references: chunk.extra_data.references
                    }
                  }

                  updatedMessage.created_at =
                    chunk.created_at ?? updatedMessage.created_at
                  if (chunk.images) {
                    updatedMessage.images = chunk.images
                  }
                  if (chunk.videos) {
                    updatedMessage.videos = chunk.videos
                  }
                  if (chunk.audio) {
                    updatedMessage.audio = chunk.audio
                  }
                } else if (
                  typeof chunk?.content !== 'string' &&
                  chunk.content
                ) {
                  const readableContent = extractReadableContent(chunk.content)
                  if (readableContent) {
                    updatedMessage.content += readableContent
                    lastContent = readableContent
                    if (updatedMessage.thinking_seconds === undefined) {
                      updatedMessage.thinking_seconds = Math.max(
                        0,
                        Math.floor((Date.now() - startedAt) / 1000)
                      )
                    }
                  }
                } else if (
                  chunk.response_audio?.transcript &&
                  typeof chunk.response_audio?.transcript === 'string'
                ) {
                  const transcript = chunk.response_audio.transcript
                  updatedMessage.response_audio = {
                    ...updatedMessage.response_audio,
                    transcript:
                      (updatedMessage.response_audio?.transcript ?? '') +
                      transcript
                  }
                }
                newMessages[newMessages.length - 1] = updatedMessage
                return newMessages
              })
            } else if (
              chunk.event === RunEvent.ReasoningStep ||
              chunk.event === RunEvent.TeamReasoningStep
            ) {
              setMessages((prevMessages) => {
                const newMessages = [...prevMessages]
                const lastMessage = newMessages[newMessages.length - 1]
                if (lastMessage && lastMessage.role === 'agent') {
                  const existingSteps =
                    lastMessage.extra_data?.reasoning_steps ?? []
                  const incomingSteps = chunk.extra_data?.reasoning_steps ?? []
                  newMessages[newMessages.length - 1] = {
                    ...lastMessage,
                    extra_data: {
                      ...lastMessage.extra_data,
                      reasoning_steps: [...existingSteps, ...incomingSteps]
                    }
                  }
                }
                return newMessages
              })
            } else if (
              chunk.event === RunEvent.ReasoningCompleted ||
              chunk.event === RunEvent.TeamReasoningCompleted
            ) {
              setMessages((prevMessages) => {
                const newMessages = [...prevMessages]
                const lastMessage = newMessages[newMessages.length - 1]
                if (lastMessage && lastMessage.role === 'agent') {
                  if (chunk.extra_data?.reasoning_steps) {
                    newMessages[newMessages.length - 1] = {
                      ...lastMessage,
                      extra_data: {
                        ...lastMessage.extra_data,
                        reasoning_steps: chunk.extra_data.reasoning_steps
                      }
                    }
                  }
                }
                return newMessages
              })
            } else if (
              chunk.event === RunEvent.RunError ||
              chunk.event === RunEvent.RunCancelled ||
              chunk.event === RunEvent.TeamRunError ||
              chunk.event === RunEvent.TeamRunCancelled
            ) {
              if (
                chunk.event === RunEvent.RunError &&
                chunk.error_id === 'off_topic'
              ) {
                // A recusa de escopo é um RunError do Agno, mas é uma resposta
                // esperada no chat. O texto é fixo para não exibir detalhes do erro.
                setMessages((prevMessages) =>
                  prevMessages.map((message, index) =>
                    index === prevMessages.length - 1 &&
                    message.role === 'agent'
                      ? {
                          ...message,
                          content:
                            'Só posso orientar sobre funcionalidades e regras de negócio do QuarkClinic.',
                          streamingError: false,
                          active_tool_name: null,
                          started_at: undefined,
                          thinking_seconds: undefined,
                          created_at: chunk.created_at ?? message.created_at
                        }
                      : message
                  )
                )
                setStreamingErrorMessage('')
                return
              }
              updateMessagesWithErrorState()
              const errorContent =
                (chunk.content as string) ||
                (chunk.event === RunEvent.TeamRunCancelled
                  ? 'Run cancelled'
                  : 'Error during run')
              setStreamingErrorMessage(errorContent)
            } else if (
              chunk.event === RunEvent.UpdatingMemory ||
              chunk.event === RunEvent.TeamMemoryUpdateStarted ||
              chunk.event === RunEvent.TeamMemoryUpdateCompleted
            ) {
              // No-op for now; could surface a lightweight UI indicator in the future
            } else if (
              chunk.event === RunEvent.RunCompleted ||
              chunk.event === RunEvent.TeamRunCompleted
            ) {
              setMessages((prevMessages) => {
                const newMessages = prevMessages.map((message, index) => {
                  if (
                    index === prevMessages.length - 1 &&
                    message.role === 'agent'
                  ) {
                    let updatedContent: string
                    if (typeof chunk.content === 'string') {
                      updatedContent = chunk.content
                    } else if (chunk.content) {
                      updatedContent =
                        extractReadableContent(chunk.content) ?? message.content
                    } else {
                      updatedContent = message.content
                    }
                    return {
                      ...message,
                      content: updatedContent,
                      active_tool_name: null,
                      thinking_seconds:
                        message.thinking_seconds ??
                        Math.max(
                          0,
                          Math.floor((Date.now() - startedAt) / 1000)
                        ),
                      tool_calls: processChunkToolCalls(
                        chunk,
                        message.tool_calls
                      ),
                      images: chunk.images ?? message.images,
                      videos: chunk.videos ?? message.videos,
                      response_audio: chunk.response_audio,
                      created_at: chunk.created_at ?? message.created_at,
                      extra_data: {
                        reasoning_steps:
                          chunk.extra_data?.reasoning_steps ??
                          message.extra_data?.reasoning_steps,
                        references:
                          chunk.extra_data?.references ??
                          message.extra_data?.references
                      }
                    }
                  }
                  return message
                })
                return newMessages
              })
            }
          },
          onError: (error) => {
            if (!isCurrentChat()) return
            updateMessagesWithErrorState()
            setStreamingErrorMessage(error.message)
          },
          onComplete: () => {}
        })
      } catch (error) {
        if (!isCurrentChat()) return
        updateMessagesWithErrorState()
        setStreamingErrorMessage(
          error instanceof Error ? error.message : String(error)
        )
      } finally {
        if (isCurrentChat()) focusChatInput()
        setIsStreaming(false)
      }
    },
    [
      setMessages,
      addMessage,
      updateMessagesWithErrorState,
      selectedEndpoint,
      streamResponse,
      agentId,
      teamId,
      mode,
      setStreamingErrorMessage,
      setIsStreaming,
      focusChatInput,
      setSessionsData,
      sessionId,
      setSessionId,
      processChunkToolCalls
    ]
  )

  return { handleStreamResponse }
}

export default useAIChatStreamHandler
