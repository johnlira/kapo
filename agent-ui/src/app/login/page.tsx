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
          className="flex items-center gap-3 rounded-xl bg-primary px-6 py-3 font-medium text-background"
          type="submit"
        >
          <svg
            aria-hidden="true"
            className="h-5 w-5"
            viewBox="0 0 48 48"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              fill="#4285F4"
              d="M43.6 24.5c0-1.4-.1-2.8-.4-4.1H24v7.8h11a9.4 9.4 0 0 1-4.1 6.2v5.1h6.6c3.9-3.6 6.1-8.8 6.1-15Z"
            />
            <path
              fill="#34A853"
              d="M24 44c5.5 0 10.1-1.8 13.5-4.9l-6.6-5.1c-1.8 1.2-4.1 2-6.9 2-5.3 0-9.8-3.6-11.4-8.5H5.8v5.3A20 20 0 0 0 24 44Z"
            />
            <path
              fill="#FBBC05"
              d="M12.6 27.5a12 12 0 0 1 0-7v-5.3H5.8a20 20 0 0 0 0 17.6l6.8-5.3Z"
            />
            <path
              fill="#EA4335"
              d="M24 12c3 0 5.7 1 7.8 3.1l5.8-5.8A19.4 19.4 0 0 0 24 4 20 20 0 0 0 5.8 15.2l6.8 5.3C14.2 15.6 18.7 12 24 12Z"
            />
          </svg>
          Entrar com Google
        </button>
      </form>
    </main>
  )
}
