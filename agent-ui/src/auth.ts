import NextAuth from 'next-auth'
import Google from 'next-auth/providers/google'

export const refreshGoogleIdToken = async (refreshToken: string) => {
  const clientId = process.env.AUTH_GOOGLE_ID ?? process.env.GOOGLE_CLIENT_ID
  const clientSecret =
    process.env.AUTH_GOOGLE_SECRET ?? process.env.GOOGLE_CLIENT_SECRET
  if (!clientId || !clientSecret)
    throw new Error('Google OAuth is not configured')

  const response = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      grant_type: 'refresh_token',
      refresh_token: refreshToken
    }),
    cache: 'no-store'
  })
  if (!response.ok) throw new Error('Google token refresh failed')

  const result: { id_token?: unknown; expires_in?: unknown } =
    await response.json()
  if (typeof result.id_token !== 'string')
    throw new Error('Google did not return a refreshed ID token')

  return {
    idToken: result.id_token,
    expiresAt:
      Math.floor(Date.now() / 1000) +
      (typeof result.expires_in === 'number' ? result.expires_in : 3600)
  }
}

const workspaceDomain = process.env.KAPO_WORKSPACE_DOMAIN?.trim().toLowerCase()
const allowedEmails = new Set(
  (process.env.KAPO_ALLOWED_EMAILS ?? '')
    .split(',')
    .map((email) => email.trim().toLowerCase())
    .filter(Boolean)
)

const authorizedEmail = (email: unknown, verified: unknown, hd: unknown) => {
  if (typeof email !== 'string' || verified !== true) return false
  const normalizedEmail = email.toLowerCase()
  return Boolean(
    (workspaceDomain &&
      hd === workspaceDomain &&
      normalizedEmail.endsWith(`@${workspaceDomain}`)) ||
      allowedEmails.has(normalizedEmail)
  )
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google({
      authorization: { params: { access_type: 'offline', prompt: 'consent' } }
    })
  ],
  pages: { signIn: '/login', error: '/login' },
  session: { strategy: 'jwt' },
  callbacks: {
    async signIn({ account, profile }) {
      if (account?.provider !== 'google' || !profile) return false
      return Boolean(
        account.id_token &&
          profile.sub &&
          authorizedEmail(profile.email, profile.email_verified, profile.hd)
      )
    },
    async jwt({ token, account, profile }) {
      if (account?.provider === 'google' && profile && account.id_token) {
        token.googleSub = profile.sub
        token.email = profile.email?.toLowerCase()
        token.name = profile.name
        token.picture = profile.picture
        token.googleHostedDomain = profile.hd
        token.googleEmailVerified = profile.email_verified === true
        token.googleIdToken = account.id_token
        token.googleIdTokenExpiresAt = account.expires_at
        if (account.refresh_token)
          token.googleRefreshToken = account.refresh_token
        delete token.agnoAccessToken
        delete token.agnoExpiresAt
        delete token.googleTokenError
      }
      return token
    },
    async session({ session, token }) {
      const email = token.email?.toLowerCase()
      const authorized = authorizedEmail(
        email,
        token.googleEmailVerified,
        token.googleHostedDomain
      )
      if (!authorized || typeof token.googleSub !== 'string') {
        return { ...session, user: undefined }
      }
      if (session.user) {
        session.user.id = token.googleSub
        session.user.email = email ?? ''
        session.user.name = typeof token.name === 'string' ? token.name : null
        session.user.image =
          typeof token.picture === 'string' ? token.picture : null
      }
      return session
    }
  }
})
