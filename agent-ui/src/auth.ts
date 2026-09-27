import NextAuth from 'next-auth'
import Google from 'next-auth/providers/google'

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
  providers: [Google],
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
        delete token.agnoAccessToken
        delete token.agnoExpiresAt
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
