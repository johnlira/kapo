import { signOut } from 'next-auth/react'

let signingOut = false

export const handleExpiredSession = (response: Response): boolean => {
  if (response.status !== 401) return false

  if (!signingOut && typeof window !== 'undefined') {
    signingOut = true
    void signOut({ callbackUrl: '/login' }).catch(() => {
      window.location.assign('/login')
    })
  }
  return true
}
