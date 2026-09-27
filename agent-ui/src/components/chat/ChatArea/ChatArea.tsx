'use client'

import ChatInput from './ChatInput'
import MessageArea from './MessageArea'
import { ThemeSelector } from '@/components/chat/Sidebar/ThemeSelector'
import { UserMenu } from './UserMenu'

const ChatArea = ({
  user
}: {
  user: { name?: string | null; email: string; image?: string | null }
}) => {
  return (
    <main className="relative m-1.5 flex flex-grow flex-col rounded-xl bg-background">
      <header className="flex shrink-0 items-center justify-end gap-2 px-4 py-3">
        <ThemeSelector />
        <UserMenu name={user.name} email={user.email} image={user.image} />
      </header>
      <MessageArea userName={user.name} />
      <div className="sticky bottom-0 ml-9 px-4 pb-2">
        <ChatInput />
      </div>
    </main>
  )
}

export default ChatArea
