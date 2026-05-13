import type { SourceType } from '$lib/api'

export interface SourceColor {
  label: string
  fill: string
  stroke: string
  text: string
  bgClass: string
}

export const SOURCE_COLORS: Record<SourceType, SourceColor> = {
  'peer-reviewed': {
    label: 'Article scientifique',
    fill: '#C0DD97',
    stroke: '#639922',
    text: '#173404',
    bgClass: 'bg-emerald-100 text-emerald-800',
  },
  institutional: {
    label: 'Institutionnel',
    fill: '#B5D4F4',
    stroke: '#378ADD',
    text: '#042C53',
    bgClass: 'bg-blue-100 text-blue-800',
  },
  press: {
    label: 'Presse',
    fill: '#FAC775',
    stroke: '#EF9F27',
    text: '#412402',
    bgClass: 'bg-amber-100 text-amber-800',
  },
  video: {
    label: 'Vidéo',
    fill: '#F2A7BE',
    stroke: '#D4456E',
    text: '#4A0E21',
    bgClass: 'bg-pink-100 text-pink-800',
  },
  image: {
    label: 'Image',
    fill: '#A7E8D9',
    stroke: '#2DAF8F',
    text: '#08382C',
    bgClass: 'bg-teal-100 text-teal-800',
  },
  original: {
    label: 'Contenu original',
    fill: '#CECBF6',
    stroke: '#7F77DD',
    text: '#26215C',
    bgClass: 'bg-purple-100 text-purple-800',
  },
}
