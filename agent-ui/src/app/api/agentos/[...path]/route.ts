import { auth } from '@/auth'
import { getToken } from 'next-auth/jwt'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

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

  const cookieName = new URL(request.url).protocol === 'https:'
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
    token.email !== session.user.email ||
    typeof token.googleIdToken !== 'string' ||
    typeof token.googleIdTokenExpiresAt !== 'number' ||
    token.googleIdTokenExpiresAt <= Math.floor(Date.now() / 1000)
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

  let exchange: Response
  try {
    exchange = await fetch(
      new URL('auth/google', `${base.replace(/\/+$/, '')}/`),
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ id_token: token.googleIdToken }),
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

  const headers = new Headers()
  headers.set('authorization', `Bearer ${result.access_token}`)
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
