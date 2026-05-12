import { writable, derived } from 'svelte/store'
import type { Card, CardDetail, Source } from '$lib/api'

interface CardsState {
  cards: Card[]
  currentCard: CardDetail | null
  loading: boolean
  error: string | null
}

function createCardsStore() {
  const { subscribe, set, update } = writable<CardsState>({
    cards: [],
    currentCard: null,
    loading: false,
    error: null
  })

  return {
    subscribe,
    setCards: (cards: Card[]) => update((s) => ({ ...s, cards, loading: false })),
    setCurrentCard: (card: CardDetail | null) => update((s) => ({ ...s, currentCard: card, loading: false })),
    setLoading: (loading: boolean) => update((s) => ({ ...s, loading })),
    setError: (error: string | null) => update((s) => ({ ...s, error, loading: false })),
    addCard: (card: Card) => update((s) => ({ ...s, cards: [card, ...s.cards] })),
    updateCard: (card: Card) => update((s) => ({
      ...s,
      cards: s.cards.map((c) => (c.id === card.id ? card : c))
    })),
    removeCard: (cardId: string) => update((s) => ({
      ...s,
      cards: s.cards.filter((c) => c.id !== cardId)
    })),
    reset: () => set({ cards: [], currentCard: null, loading: false, error: null })
  }
}

export const cards = createCardsStore()

export const draftCards = derived(cards, ($cards) =>
  $cards.cards.filter((c) => c.status === 'draft')
)

export const publishedCards = derived(cards, ($cards) =>
  $cards.cards.filter((c) => c.status === 'published')
)
