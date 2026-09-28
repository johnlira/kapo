import { auth, refreshGoogleIdToken } from '@/auth'
import { getToken } from 'next-auth/jwt'
import { createHash } from 'node:crypto'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const accessTokens = new Map<string, { token: string; expiresAt: number }>()
const MAX_CACHED_TOKENS = 100

const allowedPaths = (path: string[], method: string) => {
  if (method === 'GET') {
    return (
      (path.length === 1 &&
        ['health', 'agents', 'sessions', 'traces'].includes(path[0])) ||
      (path.length === 2 &&
        ['agents', 'sessions', 'traces'].includes(path[0])) ||
      (path.length === 3 && path[0] === 'sessions' && path[2] === 'runs')
    )
  }
  if (method === 'DELETE') {
    return path.length === 2 && path[0] === 'sessions'
  }
  if (method === 'POST') {
    return path.length === 3 && path[0] === 'agents' && path[2] === 'runs'
  }
  return false
}

async function proxy(
  request: Request,
  context: { params: Promise<{ path: string[] }> }
) {
  const session = await auth()
  if (!session?.user?.id || !session.user.email)
    return Response.json({ detail: 'Unauthorized' }, { status: 401 })

  const cookieName =
    new URL(request.url).protocol === 'https:'
      ? '__Secure-authjs.session-token'
      : 'authjs.session-token'
  const token = await getToken({
    req: { headers: { cookie: request.headers.get('cookie') ?? '' } },
    secret: process.env.AUTH_SECRET,
    cookieName,
    salt: cookieName,
    secureCookie: cookieName.startsWith('__Secure-')
  })
  if (
    !token ||
    token.googleSub !== session.user.id ||
    token.email !== session.user.email
  )
    return Response.json({ detail: 'Google session expired' }, { status: 401 })

  const base = process.env.AGENTOS_URL
  if (!base)
    return Response.json(
      { detail: 'AgentOS is not configured' },
      { status: 503 }
    )

  const { path } = await context.params
  if (
    !Array.isArray(path) ||
    !allowedPaths(path, request.method) ||
    path.some(
      (segment) =>
        !segment ||
        segment === '.' ||
        segment === '..' ||
        segment.includes('/') ||
        segment.includes('\\')
    )
  ) {
    return Response.json({ detail: 'Not found' }, { status: 404 })
  }

  let target: URL
  try {
    const origin = new URL(base)
    if (
      !['http:', 'https:'].includes(origin.protocol) ||
      origin.username ||
      origin.password ||
      origin.search ||
      origin.hash ||
      origin.pathname.split('/').some((part) => part === '..' || part === '.')
    ) {
      throw new Error('Invalid AgentOS URL')
    }
    target = new URL(origin)
    target.pathname = `${origin.pathname.replace(/\/$/, '')}/${path.map(encodeURIComponent).join('/')}`
  } catch {
    return Response.json(
      { detail: 'AgentOS is not configured' },
      { status: 503 }
    )
  }
  target.search = new URL(request.url).search

  const identity = createHash('sha256')
    .update(
      `${base}\0${cookieName}\0${token.googleSub}\0${token.googleRefreshToken ?? token.googleIdToken}`
    )
    .digest('hex')
  const cached = accessTokens.get(identity)
  const now = Math.floor(Date.now() / 1000)
  if (cached && cached.expiresAt <= now + 60) accessTokens.delete(identity)
  if (
    typeof token.googleIdTokenExpiresAt !== 'number' ||
    typeof token.googleIdToken !== 'string'
  )
    return Response.json({ detail: 'Google session expired' }, { status: 401 })

  let accessToken = cached && cached.expiresAt > now + 60 ? cached.token : null
  if (!accessToken) {
    let googleIdToken = token.googleIdToken
    if (token.googleIdTokenExpiresAt <= now + 60) {
      if (typeof token.googleRefreshToken !== 'string')
        return Response.json(
          { detail: 'Google session expired. Please sign in again.' },
          { status: 401 }
        )
      try {
        googleIdToken = (await refreshGoogleIdToken(token.googleRefreshToken))
          .idToken
      } catch {
        return Response.json(
          { detail: 'Google session expired. Please sign in again.' },
          { status: 401 }
        )
      }
    }
    let exchange: Response
    try {
      exchange = await fetch(
        new URL('auth/google', `${base.replace(/\/+$/, '')}/`),
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ id_token: googleIdToken }),
          cache: 'no-store'
        }
      )
    } catch {
      return Response.json({ detail: 'AgentOS unavailable' }, { status: 502 })
    }
    if (!exchange.ok)
      return Response.json(
        { detail: 'Google session rejected' },
        { status: exchange.status === 401 ? 401 : 502 }
      )
    let result: { access_token?: unknown; expires_in?: unknown }
    try {
      result = await exchange.json()
    } catch {
      return Response.json(
        { detail: 'Invalid AgentOS response' },
        { status: 502 }
      )
    }
    if (
      typeof result.access_token !== 'string' ||
      typeof result.expires_in !== 'number' ||
      result.expires_in <= 0
    )
      return Response.json(
        { detail: 'Invalid AgentOS response' },
        { status: 502 }
      )
    accessToken = result.access_token
    accessTokens.delete(identity)
    accessTokens.set(identity, {
      token: accessToken,
      expiresAt: now + result.expires_in
    })
    if (accessTokens.size > MAX_CACHED_TOKENS) {
      const oldest = accessTokens.keys().next().value
      if (oldest) accessTokens.delete(oldest)
    }
  }

  const headers = new Headers()
  headers.set('authorization', `Bearer ${accessToken}`)
  const contentType = request.headers.get('content-type')
  if (contentType && request.method === 'POST')
    headers.set('content-type', contentType)

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === 'POST' ? request.body : undefined,
      // Required by Node fetch for streaming multipart uploads.
      ...(request.method === 'POST' ? { duplex: 'half' as const } : {}),
      cache: 'no-store',
      signal: request.signal
    } as RequestInit)
    if (upstream.status === 401 && cached) accessTokens.delete(identity)
    const responseHeaders = new Headers()
    const responseType = upstream.headers.get('content-type')
    if (responseType) responseHeaders.set('content-type', responseType)
    responseHeaders.set('cache-control', 'no-store')
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders
    })
  } catch {
    return Response.json({ detail: 'AgentOS unavailable' }, { status: 502 })
  }
}

export { proxy as GET, proxy as POST, proxy as DELETE }
