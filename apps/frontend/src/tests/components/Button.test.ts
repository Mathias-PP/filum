import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/svelte'
import Button from '$lib/components/Button.svelte'

describe('Button', () => {
  it('renders with text', () => {
    const { getByText } = render(Button, {
      props: { children: () => 'Click me' }
    })
    expect(getByText('Click me')).toBeTruthy()
  })
})
