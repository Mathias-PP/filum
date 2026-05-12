import { env } from '$env/dynamic/public'

import type { LayoutLoad } from './$types'

export const ssr = false

export const load: LayoutLoad = async ({ fetch }) => {
  const base = env.PUBLIC_API_BASE_URL ?? ''
  const response = await fetch(`${base}/api/v1/auth/me`, {
    credentials: 'include'
  })

  if (response.ok) {
    const user = await response.json()
    return { user }
  }

  return { user: null }
}
