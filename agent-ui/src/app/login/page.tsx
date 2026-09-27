import { auth, signIn } from '@/auth'
import { redirect } from 'next/navigation'

export default async function Login({
  searchParams
}: {
  searchParams: Promise<{ error?: string }>
}) {
  if ((await auth())?.user?.id) redirect('/')
  const { error } = await searchParams
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4">
      {error && (
        <p
          role="alert"
          className="max-w-md text-center text-sm text-destructive"
        >
          {error === 'AccessDenied'
            ? 'Esta conta Google não tem acesso ao agente. Entre com um e-mail autorizado ou peça acesso ao administrador.'
            : 'Não foi possível entrar com Google. Tente novamente.'}
        </p>
      )}
      <form
        action={async () => {
          'use server'
          await signIn(
            'google',
            { redirectTo: '/' },
            { prompt: 'select_account' }
          )
        }}
      >
        <button
          className="rounded-xl bg-primary px-6 py-3 font-medium text-background"
          type="submit"
        >
          Entrar com Google
        </button>
      </form>
    </main>
  )
}
