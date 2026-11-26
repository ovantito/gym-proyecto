/** Báscula simulada: no hay hardware real. Los valores de cada socio se derivan de su id para que
 *  sean estables entre visitas (si no, el backend vería saltos de peso y los marcaría como atípicos). */
export interface Lectura {
  peso: number
  grasa: number
  musculo: number
  pulso: number
  sistolica: number
  diastolica: number
}

function hash(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619)
  return h >>> 0
}

const r1 = (n: number) => Math.round(n * 10) / 10
const ruido = (amp: number) => (Math.random() - 0.5) * 2 * amp

export function lecturaNormal(socioId: string): Lectura {
  const h = hash(socioId)
  const pesoBase = 55 + (h % 400) / 10 // 55–95 kg
  const grasaBase = 15 + ((h >>> 9) % 170) / 10 // 15–32 %
  const peso = r1(pesoBase + ruido(0.4))
  const grasa = r1(grasaBase + ruido(0.3))
  return {
    peso,
    grasa,
    musculo: r1(peso * (1 - grasa / 100) * 0.53),
    pulso: Math.round(64 + ruido(8)),
    sistolica: Math.round(118 + ruido(8)),
    diastolica: Math.round(77 + ruido(5)),
  }
}

/** Lectura imposible: el peso salta +6.5 kg respecto a la lectura normal (báscula descalibrada). */
export function lecturaImposible(socioId: string): Lectura {
  const base = lecturaNormal(socioId)
  const peso = r1(base.peso + 6.5)
  return { ...base, peso, musculo: r1(peso * (1 - base.grasa / 100) * 0.53) }
}

/** Presión alta (165/102): lectura normal en todo lo demás; las reglas fijas del backend dan semáforo rojo. */
export function lecturaPresionAlta(socioId: string): Lectura {
  return { ...lecturaNormal(socioId), sistolica: 165, diastolica: 102 }
}
