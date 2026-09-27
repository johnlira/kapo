import type { ChatMessage } from '@/types/os'

import { AgentMessage, UserMessage } from './MessageItem'
import Tooltip from '@/components/ui/tooltip'
import {
  ReasoningStepProps,
  ReasoningProps,
  ReferenceData,
  Reference
} from '@/types/os'
import React, { type FC } from 'react'
import { useEffect, useState } from 'react'

import Icon from '@/components/ui/icon'
import ChatBlankState from './ChatBlankState'
import { useStore } from '@/store'

interface MessageListProps {
  messages: ChatMessage[]
  userName?: string | null
}

interface MessageWrapperProps {
  message: ChatMessage
  isLastMessage: boolean
}

interface ReferenceProps {
  references: ReferenceData[]
}

interface ReferenceItemProps {
  reference: Reference
}

const ReferenceItem: FC<ReferenceItemProps> = ({ reference }) => (
  <div className="relative flex h-[63px] w-[190px] cursor-default flex-col justify-between overflow-hidden rounded-md bg-background-secondary p-3 transition-colors hover:bg-background-secondary/80">
    <p className="text-sm font-medium text-primary">{reference.name}</p>
    <p className="truncate text-xs text-primary/40">{reference.content}</p>
  </div>
)

const References: FC<ReferenceProps> = ({ references }) => (
  <div className="flex flex-col gap-4">
    {references.map((referenceData, index) => (
      <div
        key={`${referenceData.query}-${index}`}
        className="flex flex-col gap-3"
      >
        <div className="flex flex-wrap gap-3">
          {referenceData.references.map((reference, refIndex) => (
            <ReferenceItem
              key={`${reference.name}-${reference.meta_data.chunk}-${refIndex}`}
              reference={reference}
            />
          ))}
        </div>
      </div>
    ))}
  </div>
)

const toolLabels: Record<string, string> = {
  search_functionality_catalog: 'Buscando funcionalidades',
  search_repository_files: 'Consultando código do QuarkClinic',
  catalog_repositories: 'Verificando fontes disponíveis',
  project_inventory: 'Conferindo módulos do sistema',
  read_repository_paths: 'Lendo detalhes relevantes'
}

const AgentMessageWrapper = ({
  message,
  isLastMessage
}: MessageWrapperProps) => {
  const isStreaming = useStore((state) => state.isStreaming)
  const isActive = isStreaming && isLastMessage
  const toolCalls = message.tool_calls ?? []
  const activeToolName = message.active_tool_name
  const currentToolLabel = activeToolName
    ? (toolLabels[activeToolName] ?? activeToolName.replaceAll('_', ' '))
    : 'Preparando resposta'
  const [elapsedSeconds, setElapsedSeconds] = useState(
    message.thinking_seconds ?? 0
  )
  const startedAt = message.started_at

  useEffect(() => {
    if (!isActive || !startedAt || message.thinking_seconds !== undefined)
      return
    const updateElapsed = () =>
      setElapsedSeconds(
        Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
      )
    updateElapsed()
    const interval = window.setInterval(updateElapsed, 1000)
    return () => window.clearInterval(interval)
  }, [isActive, startedAt, message.thinking_seconds])

  const thinkingSeconds = message.thinking_seconds ?? elapsedSeconds

  return (
    <div className="flex flex-col gap-y-6">
      {message.extra_data?.reasoning_steps &&
        message.extra_data.reasoning_steps.length > 0 && (
          <div className="flex items-start gap-4">
            <Tooltip delayDuration={0} content={<p>Reasoning</p>} side="top">
              <Icon type="reasoning" size="sm" />
            </Tooltip>
            <div className="flex flex-col gap-3">
              <p className="text-xs uppercase">Reasoning</p>
              <Reasonings reasoning={message.extra_data.reasoning_steps} />
            </div>
          </div>
        )}
      {message.extra_data?.references &&
        message.extra_data.references.length > 0 && (
          <div className="flex items-start gap-4">
            <Tooltip delayDuration={0} content={<p>References</p>} side="top">
              <Icon type="references" size="sm" />
            </Tooltip>
            <div className="flex flex-col gap-3">
              <References references={message.extra_data.references} />
            </div>
          </div>
        )}
      {((isActive && !message.content) ||
        toolCalls.length > 0 ||
        message.thinking_seconds !== undefined) && (
        <details className="group max-w-xl text-muted">
          <summary className="flex cursor-pointer list-none items-center gap-2 text-sm [&::-webkit-details-marker]:hidden">
            <span className="font-medium">
              {isActive
                ? `${currentToolLabel} · ${thinkingSeconds}s`
                : message.thinking_seconds !== undefined || message.started_at
                  ? `Pensou por ${thinkingSeconds}s`
                  : 'Investigação concluída'}
            </span>
            <Icon
              type="chevron-down"
              size="xs"
              className="transition-transform group-open:rotate-180"
            />
          </summary>
          <ol className="ml-1 mt-2 space-y-2 border-l border-border pl-4 text-sm">
            {toolCalls.map((toolCall, index) => (
              <li
                key={
                  toolCall.tool_call_id ||
                  `${toolCall.tool_name}-${toolCall.created_at}-${index}`
                }
                className="flex items-center gap-2 text-muted"
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${toolCall.tool_call_error ? 'bg-destructive' : 'bg-positive'}`}
                />
                {toolLabels[toolCall.tool_name] ??
                  toolCall.tool_name.replaceAll('_', ' ')}
              </li>
            ))}
          </ol>
        </details>
      )}
      <AgentMessage message={message} isActive={isActive} />
    </div>
  )
}
const Reasoning: FC<ReasoningStepProps> = ({ index, stepTitle }) => (
  <div className="flex items-center gap-2 text-secondary">
    <div className="flex h-[20px] items-center rounded-md bg-background-secondary p-2">
      <p className="text-xs">STEP {index + 1}</p>
    </div>
    <p className="text-xs">{stepTitle}</p>
  </div>
)
const Reasonings: FC<ReasoningProps> = ({ reasoning }) => (
  <div className="flex flex-col items-start justify-center gap-2">
    {reasoning.map((title, index) => (
      <Reasoning
        key={`${title.title}-${title.action}-${index}`}
        stepTitle={title.title}
        index={index}
      />
    ))}
  </div>
)

const Messages = ({ messages, userName }: MessageListProps) => {
  if (messages.length === 0) {
    return <ChatBlankState userName={userName} />
  }

  return (
    <>
      {messages.map((message, index) => {
        const key = `${message.role}-${message.created_at}-${index}`
        const isLastMessage = index === messages.length - 1

        if (message.role === 'agent') {
          return (
            <AgentMessageWrapper
              key={key}
              message={message}
              isLastMessage={isLastMessage}
            />
          )
        }
        return <UserMessage key={key} message={message} />
      })}
    </>
  )
}

export default Messages
