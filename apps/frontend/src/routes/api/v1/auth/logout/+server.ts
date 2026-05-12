import type { RequestHandler } from '@sveltejs/kit'

export const POST: RequestHandler = async ({ fetch, cookies }) => {
  try {
    const response = await fetch('/api/v1/auth/logout', {
      method: 'POST',
      credentials: 'include'
    })
    
    cookies.delete('filum_session', { path: '/' })
    
    return new Response(null, {
      status: 303,
      headers: { Location: '/' }
    })
  } catch {
    return new Response(null, {
      status: 303,
      headers: { Location: '/' }
    })
  }
}
