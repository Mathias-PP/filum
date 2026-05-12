import adapter from '@sveltejs/adapter-auto'
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte'

const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter(),
    alias: {
      $lib: 'src/lib',
      '$components': 'src/lib/components',
      '$stores': 'src/lib/stores',
      '$api': 'src/lib/api',
      '$utils': 'src/lib/utils'
    },
    csrf: {
      checkOrigin: false
    },
    vitePlugin: {
      inspector: {
        toggleKey: 'shiftAlt',
        toggleButtonOk: 'inspect',
        toggleButtonCancel: 'close'
      }
    }
  }
}

export default config
