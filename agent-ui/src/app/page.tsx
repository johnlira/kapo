import Sidebar from '@/components/chat/Sidebar/Sidebar'
import { ChatArea } from '@/components/chat/ChatArea'
import { Suspense } from 'react'
import { auth } from '@/auth'
import { redirect } from 'next/navigation'

export default async function Home() {
  const session = await auth()
  if (!session?.user?.email) redirect('/login')
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <div className="flex h-screen bg-background/80">
        <Sidebar />
        <ChatArea
          user={{
            name: session.user.name,
            email: session.user.email,
            image: session.user.image
          }}
        />
      </div>
    </Suspense>
  )
}
