import { useCallback } from 'react'
import { toast } from 'sonner'

import { useStore } from '../store'

import { AgentDetails, type ChatMessage } from '@/types/os'
import { getAgentsAPI, getStatusAPI } from '@/api/os'
import { useQueryState } from 'nuqs'
import { invalidateSessionRequest } from './useSessionLoader'

const useChatActions = () => {
  const { chatInputRef } = useStore()
  const selectedEndpoint = useStore((state) => state.selectedEndpoint)
  const [, setSessionId] = useQueryState('session')
  const setMessages = useStore((state) => state.setMessages)
  const setIsEndpointActive = useStore((state) => state.setIsEndpointActive)
  const setIsEndpointLoading = useStore((state) => state.setIsEndpointLoading)
  const setAgents = useStore((state) => state.setAgents)
  const setTeams = useStore((state) => state.setTeams)
  const setSelectedModel = useStore((state) => state.setSelectedModel)
  const setMode = useStore((state) => state.setMode)
  const [, setAgentId] = useQueryState('agent')
  const [, setTeamId] = useQueryState('team')
  const [, setDbId] = useQueryState('db_id')

  const getStatus = useCallback(async () => {
    try {
      const status = await getStatusAPI(selectedEndpoint)
      return status
    } catch {
      return 503
    }
  }, [selectedEndpoint])

  const getAgents = useCallback(async () => {
    try {
      const agents = await getAgentsAPI(selectedEndpoint)
      return agents
    } catch {
      toast.error('Error fetching agents')
      return []
    }
  }, [selectedEndpoint])

  const clearChat = useCallback(() => {
    invalidateSessionRequest()
    useStore.getState().setSelectedSessionId(null)
    setMessages([])
    setSessionId(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const focusChatInput = useCallback(() => {
    setTimeout(() => {
      requestAnimationFrame(() => chatInputRef?.current?.focus())
    }, 0)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const addMessage = useCallback(
    (message: ChatMessage) => {
      setMessages((prevMessages) => [...prevMessages, message])
    },
    [setMessages]
  )

  const initialize = useCallback(async () => {
    setIsEndpointLoading(true)
    try {
      const status = await getStatus()
      let agents: AgentDetails[] = []
      if (status === 200) {
        agents = await getAgents()

        setAgents(agents)
        setTeams([])
        const kapo = agents.find(
          (agent) => agent.id === 'kapo' || agent.name?.toLowerCase() === 'kapo'
        )
        setMode('agent')
        await setTeamId(null)
        await setAgentId(kapo?.id ?? null)
        setSelectedModel(kapo?.model?.model || '')
        await setDbId(kapo?.db_id ?? null)
        setIsEndpointActive(Boolean(kapo))
      } else {
        setIsEndpointActive(false)
        setMode('agent')
        setSelectedModel('')
        setAgentId(null)
        setTeamId(null)
        setDbId(null)
      }
      return { agents }
    } catch (error) {
      console.error('Error initializing :', error)
      setIsEndpointActive(false)
      setMode('agent')
      setSelectedModel('')
      setAgentId(null)
      setTeamId(null)
      setDbId(null)
      setAgents([])
      setTeams([])
    } finally {
      setIsEndpointLoading(false)
    }
  }, [
    getStatus,
    getAgents,
    setIsEndpointActive,
    setIsEndpointLoading,
    setAgents,
    setTeams,
    setAgentId,
    setSelectedModel,
    setMode,
    setTeamId,
    setDbId
  ])

  return {
    clearChat,
    addMessage,
    getAgents,
    focusChatInput,
    initialize
  }
}

export default useChatActions
