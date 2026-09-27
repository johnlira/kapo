'use client'

import { FC, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryState } from 'nuqs'

import { useStore } from '@/store'
import useSessionLoader from '@/hooks/useSessionLoader'

import SessionItem from './SessionItem'
import SessionBlankState from './SessionBlankState'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { SessionEntry } from '@/types/os'
import { Search } from 'lucide-react'

const sections = ['Hoje', 'Ontem', 'Últimos 7 dias', 'Mais antigas'] as const

const sessionTime = (entry: SessionEntry) => {
  const timestamp = entry.updated_at || entry.created_at
  return timestamp ? timestamp * (timestamp < 1e12 ? 1000 : 1) : 0
}

const sessionSection = (timestamp: number, today: number) => {
  if (!timestamp || !Number.isFinite(timestamp)) return 'Mais antigas'
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return 'Mais antigas'
  const todayDate = new Date(today)
  const daysAgo = Math.round(
    (Date.UTC(
      todayDate.getFullYear(),
      todayDate.getMonth(),
      todayDate.getDate()
    ) -
      Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())) /
      86400000
  )
  if (daysAgo <= 0) return 'Hoje'
  if (daysAgo === 1) return 'Ontem'
  return daysAgo < 7 ? 'Últimos 7 dias' : 'Mais antigas'
}

interface SkeletonListProps {
  skeletonCount: number
}
const SkeletonList: FC<SkeletonListProps> = ({ skeletonCount }) => {
  const list = useMemo(
    () => Array.from({ length: skeletonCount }, (_, i) => i),
    [skeletonCount]
  )

  return list.map((k, idx) => (
    <Skeleton
      key={k}
      className={cn(
        'mb-1 h-12 rounded-lg px-3 py-2',
        idx > 0 && 'bg-background-secondary'
      )}
    />
  ))
}

const Sessions = () => {
  const [agentId] = useQueryState('agent', {
    parse: (v: string | null) => v || undefined,
    history: 'push'
  })
  const [teamId] = useQueryState('team')
  const [sessionId] = useQueryState('session')
  const [dbId] = useQueryState('db_id')

  const {
    selectedEndpoint,
    mode,
    isEndpointActive,
    isEndpointLoading,
    hydrated,
    sessionsData,
    setSessionsData,
    isSessionsLoading
  } = useStore()

  const [isScrolling, setIsScrolling] = useState(false)
  const [search, setSearch] = useState('')

  const { getSessions, getSession } = useSessionLoader()
  const scrollTimeoutRef = useRef<ReturnType<typeof setTimeout>>(null)

  const handleScroll = () => {
    setIsScrolling(true)

    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current)
    }

    scrollTimeoutRef.current = setTimeout(() => {
      setIsScrolling(false)
    }, 1500)
  }

  // Cleanup the scroll timeout when component unmounts
  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (hydrated && sessionId && selectedEndpoint && (agentId || teamId)) {
      const entityType = agentId ? 'agent' : 'team'
      getSession({ entityType, agentId, teamId, dbId }, sessionId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated, sessionId, selectedEndpoint, agentId, teamId, dbId])

  useEffect(() => {
    if (!selectedEndpoint || isEndpointLoading) return
    if (!(agentId || teamId || dbId)) {
      setSessionsData([])
      return
    }
    setSessionsData([])
    getSessions({
      entityType: mode,
      agentId,
      teamId,
      dbId
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    selectedEndpoint,
    agentId,
    teamId,
    mode,
    isEndpointLoading,
    getSessions,
    dbId
  ])

  const groupedSessions = useMemo(() => {
    const now = new Date()
    const today = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate()
    ).getTime()
    const groups: Record<(typeof sections)[number], SessionEntry[]> = {
      Hoje: [],
      Ontem: [],
      'Últimos 7 dias': [],
      'Mais antigas': []
    }
    const query = search.trim().toLocaleLowerCase()
    for (const entry of [...(sessionsData ?? [])].sort(
      (a, b) => sessionTime(b) - sessionTime(a)
    )) {
      if ((entry.session_name ?? '').toLocaleLowerCase().includes(query)) {
        groups[sessionSection(sessionTime(entry), today)].push(entry)
      }
    }
    return groups
  }, [sessionsData, search])

  const searchField = (
    <label className="relative mb-4 block">
      <Search
        aria-hidden="true"
        className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
      />
      <input
        type="search"
        aria-label="Buscar conversas"
        placeholder="Buscar conversas"
        disabled={isSessionsLoading || isEndpointLoading}
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        className="h-10 w-full rounded-xl border border-border bg-background pl-9 pr-3 text-sm text-secondary outline-none placeholder:text-muted focus-visible:border-brand focus-visible:ring-1 focus-visible:ring-brand"
      />
    </label>
  )

  if (isSessionsLoading || isEndpointLoading) {
    return (
      <div className="flex min-h-0 w-full flex-1 flex-col">
        <div className="mb-3 text-sm font-semibold text-primary">Conversas</div>
        {searchField}
        <div className="min-h-0 flex-1 overflow-y-auto">
          <SkeletonList skeletonCount={5} />
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 w-full flex-1 flex-col">
      <div className="mb-3 w-full text-sm font-semibold text-primary">
        Conversas
      </div>
      {searchField}
      <div
        className={`min-h-0 flex-1 overflow-y-auto transition-all duration-300 [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar]:transition-opacity [&::-webkit-scrollbar]:duration-300 ${
          isScrolling
            ? '[&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-background [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar]:opacity-0'
            : '[&::-webkit-scrollbar]:opacity-100'
        }`}
        onScroll={handleScroll}
        onMouseOver={() => setIsScrolling(true)}
        onMouseLeave={handleScroll}
      >
        {!isEndpointActive ||
        (!isSessionsLoading &&
          (!sessionsData || sessionsData?.length === 0)) ? (
          <SessionBlankState />
        ) : sections.some((section) => groupedSessions[section].length > 0) ? (
          <div className="space-y-5 pr-1">
            {sections.map((section) =>
              groupedSessions[section].length > 0 ? (
                <section key={section} aria-label={section}>
                  <h3 className="mb-2 px-3 text-xs font-medium text-muted">
                    {section}
                  </h3>
                  <div className="flex flex-col gap-1">
                    {groupedSessions[section].map((entry) => (
                      <SessionItem
                        key={entry.session_id}
                        {...entry}
                        currentSessionId={sessionId}
                        isSelected={sessionId === entry.session_id}
                      />
                    ))}
                  </div>
                </section>
              ) : null
            )}
          </div>
        ) : (
          <p className="px-3 py-4 text-sm text-muted">
            Nenhuma conversa encontrada.
          </p>
        )}
      </div>
    </div>
  )
}

export default Sessions
