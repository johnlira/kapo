import { create } from 'zustand'

import {
  AgentDetails,
  SessionEntry,
  TeamDetails,
  type ChatMessage
} from '@/types/os'

interface Store {
  hydrated: boolean
  setHydrated: () => void
  streamingErrorMessage: string
  setStreamingErrorMessage: (streamingErrorMessage: string) => void
  isStreaming: boolean
  setIsStreaming: (isStreaming: boolean) => void
  isEndpointActive: boolean
  setIsEndpointActive: (isActive: boolean) => void
  isEndpointLoading: boolean
  setIsEndpointLoading: (isLoading: boolean) => void
  messages: ChatMessage[]
  selectedSessionId: string | null
  setSelectedSessionId: (sessionId: string | null) => void
  setMessages: (
    messages: ChatMessage[] | ((prevMessages: ChatMessage[]) => ChatMessage[])
  ) => void
  chatInputRef: React.RefObject<HTMLTextAreaElement | null>
  selectedEndpoint: string
  agents: AgentDetails[]
  setAgents: (agents: AgentDetails[]) => void
  teams: TeamDetails[]
  setTeams: (teams: TeamDetails[]) => void
  selectedModel: string
  setSelectedModel: (model: string) => void
  mode: 'agent' | 'team'
  setMode: (mode: 'agent' | 'team') => void
  sessionsData: SessionEntry[] | null
  setSessionsData: (
    sessionsData:
      | SessionEntry[]
      | ((prevSessions: SessionEntry[] | null) => SessionEntry[] | null)
  ) => void
  isSessionsLoading: boolean
  setIsSessionsLoading: (isSessionsLoading: boolean) => void
}

export const useStore = create<Store>()((set) => ({
  hydrated: false,
  setHydrated: () => set({ hydrated: true }),
  streamingErrorMessage: '',
  setStreamingErrorMessage: (streamingErrorMessage) =>
    set(() => ({ streamingErrorMessage })),
  isStreaming: false,
  setIsStreaming: (isStreaming) => set(() => ({ isStreaming })),
  isEndpointActive: false,
  setIsEndpointActive: (isActive) =>
    set(() => ({ isEndpointActive: isActive })),
  isEndpointLoading: true,
  setIsEndpointLoading: (isLoading) =>
    set(() => ({ isEndpointLoading: isLoading })),
  messages: [],
  selectedSessionId: null,
  setSelectedSessionId: (selectedSessionId) => set({ selectedSessionId }),
  setMessages: (messages) =>
    set((state) => ({
      messages:
        typeof messages === 'function' ? messages(state.messages) : messages
    })),
  chatInputRef: { current: null },
  selectedEndpoint: '/api/agentos',
  agents: [],
  setAgents: (agents) => set({ agents }),
  teams: [],
  setTeams: (teams) => set({ teams }),
  selectedModel: '',
  setSelectedModel: (selectedModel) => set(() => ({ selectedModel })),
  mode: 'agent',
  setMode: (mode) => set(() => ({ mode })),
  sessionsData: null,
  setSessionsData: (sessionsData) =>
    set((state) => ({
      sessionsData:
        typeof sessionsData === 'function'
          ? sessionsData(state.sessionsData)
          : sessionsData
    })),
  isSessionsLoading: false,
  setIsSessionsLoading: (isSessionsLoading) =>
    set(() => ({ isSessionsLoading }))
}))
