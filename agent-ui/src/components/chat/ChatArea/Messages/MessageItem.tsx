import MarkdownRenderer from '@/components/ui/typography/MarkdownRenderer'
import { useStore } from '@/store'
import type { ChatMessage } from '@/types/os'
import Videos from './Multimedia/Videos'
import Images from './Multimedia/Images'
import Audios from './Multimedia/Audios'
import { memo, useRef, useState, type RefObject } from 'react'
import { Check, Copy } from 'lucide-react'
import AgentThinkingLoader from './AgentThinkingLoader'

interface MessageProps {
  message: ChatMessage
}

const CopyMessageButton = ({
  content,
  renderedContent
}: {
  content: string
  renderedContent?: RefObject<HTMLDivElement | null>
}) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(
        renderedContent?.current?.innerText?.trim() || content
      )
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={copied ? 'Copiado' : 'Copiar mensagem'}
      title={copied ? 'Copiado' : 'Copiar mensagem'}
      className="flex items-center gap-1.5 rounded-md p-1.5 text-sm text-muted transition-colors hover:bg-background-secondary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      {copied ? <Check size={16} /> : <Copy size={16} />}
      <span>{copied ? 'Copiado' : 'Copiar'}</span>
    </button>
  )
}

const AgentMessage = ({
  message,
  isActive = false
}: MessageProps & { isActive?: boolean }) => {
  const { streamingErrorMessage } = useStore()
  const renderedContent = useRef<HTMLDivElement>(null)
  let messageContent
  if (message.streamingError) {
    messageContent = (
      <p className="text-destructive">
        Oops! Something went wrong while streaming.{' '}
        {streamingErrorMessage ? (
          <>{streamingErrorMessage}</>
        ) : (
          'Please try refreshing the page or try again later.'
        )}
      </p>
    )
  } else if (message.content) {
    messageContent = (
      <div className="flex w-full flex-col gap-4">
        <MarkdownRenderer>{message.content}</MarkdownRenderer>
        {message.videos && message.videos.length > 0 && (
          <Videos videos={message.videos} />
        )}
        {message.images && message.images.length > 0 && (
          <Images images={message.images} />
        )}
        {message.audio && message.audio.length > 0 && (
          <Audios audio={message.audio} />
        )}
      </div>
    )
  } else if (message.response_audio) {
    if (!message.response_audio.transcript) {
      messageContent = (
        <div className="mt-2 flex items-start">
          <AgentThinkingLoader />
        </div>
      )
    } else {
      messageContent = (
        <div className="flex w-full flex-col gap-4">
          <MarkdownRenderer>
            {message.response_audio.transcript}
          </MarkdownRenderer>
          {message.response_audio.content && message.response_audio && (
            <Audios audio={[message.response_audio]} />
          )}
        </div>
      )
    }
  } else {
    messageContent = (
      <div className="mt-2">
        <AgentThinkingLoader />
      </div>
    )
  }

  return (
    <div className="min-w-0 font-geist text-secondary">
      <div
        ref={renderedContent}
        className="text-[16px] leading-7 sm:text-[18px] sm:leading-8"
      >
        {messageContent}
      </div>
      {(message.content || message.response_audio?.transcript) && !isActive && (
        <div className="mt-2">
          <CopyMessageButton
            content={
              message.content || message.response_audio?.transcript || ''
            }
            renderedContent={renderedContent}
          />
        </div>
      )}
    </div>
  )
}

const UserMessage = memo(({ message }: MessageProps) => {
  return (
    <div className="flex justify-end text-start">
      <div className="group flex max-w-[85%] flex-col items-end sm:max-w-[70%]">
        <div className="w-full whitespace-pre-wrap break-words rounded-[26px] bg-[#e7f3ff] px-5 py-3 font-geist text-[16px] leading-7 text-[#152b48] dark:bg-[#263c50] dark:text-[#f1f6fc] sm:text-[18px] sm:leading-8">
          {message.content}
        </div>
        {message.content && (
          <div className="mt-2 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
            <CopyMessageButton content={message.content} />
          </div>
        )}
      </div>
    </div>
  )
})

AgentMessage.displayName = 'AgentMessage'
UserMessage.displayName = 'UserMessage'
export { AgentMessage, UserMessage }
