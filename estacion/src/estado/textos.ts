import type { Semaforo } from '../api/cliente'

/** PAR-Q+ (primera página, 7 preguntas). Las 3 primeras son las "críticas" del backend (umbrales.py). */
export const PREGUNTAS_PARQ = [
  '¿Un médico te dijo que tienes una condición del corazón o que solo hagas actividad supervisada?',
  '¿Sientes dolor en el pecho cuando haces actividad física?',
  'En el último mes, ¿tuviste dolor de pecho estando en reposo?',
  '¿Pierdes el equilibrio por mareos o has perdido el conocimiento alguna vez?',
  '¿Tienes un problema de huesos o articulaciones que empeora con la actividad?',
  '¿Tomas medicamentos para la presión o el corazón?',
  '¿Hay otra razón por la que no deberías hacer actividad física?',
]

/** Mismos ids y nombres que backend/app/core/lesiones.py. */
export const LESIONES = [
  { id: 'rodilla', texto: 'Rodilla' },
  { id: 'hombro', texto: 'Hombro' },
  { id: 'espalda_baja', texto: 'Espalda baja (lumbar)' },
  { id: 'cuello', texto: 'Cuello (cervical)' },
  { id: 'muneca_codo', texto: 'Muñeca o codo' },
  { id: 'tobillo', texto: 'Tobillo' },
  { id: 'cadera', texto: 'Cadera' },
] as const

export const nombreLesion = (id: string) => LESIONES.find((l) => l.id === id)?.texto ?? id

export type SintomaHoy = 'dolor_cabeza' | 'mareo'

/**
 * "¿Cómo te sientes hoy?". Los síntomas (`sintoma`) dan amarillo SOLO hoy y no se guardan en la ficha permanente.
 * El dolor de pecho sí cuenta como respuesta del PAR-Q+ (`parq` = índice de la pregunta, desde 0).
 */
export const ANIMOS = [
  { id: 'bien', texto: 'Bien', parq: null, sintoma: null },
  { id: 'cansado', texto: 'Cansado/a', parq: null, sintoma: null },
  { id: 'dolor_cabeza', texto: 'Dolor de cabeza fuerte', parq: null, sintoma: 'dolor_cabeza' },
  { id: 'mareo', texto: 'Mareo', parq: null, sintoma: 'mareo' },
  { id: 'pecho', texto: 'Dolor en el pecho', parq: 1, sintoma: null }, // pregunta 2 (dolor de pecho al hacer actividad)
] as const

/** Convierte el motivo técnico del backend en palabras simples. */
export function motivoSimple(motivo: string): string {
  if (motivo.startsWith('Presión')) return 'Tu presión está alta hoy.'
  if (motivo.startsWith('Pulso')) return 'Tu pulso en reposo está muy acelerado.'
  if (motivo.startsWith('PAR-Q+ con respuesta crítica')) return 'Una de tus respuestas sobre el corazón o el pecho necesita revisión médica.'
  if (motivo.startsWith('PAR-Q+')) return 'Marcaste una molestia en el cuestionario.'
  if (motivo.startsWith('Lesión declarada')) {
    const nombres = (motivo.split(': ')[1] ?? '').split(', ').filter(Boolean).map((l) => nombreLesion(l).toLowerCase())
    return `Por tu lesión de ${nombres.join(', ') || 'tu cuerpo'}, cuidaremos tu rutina.`
  }
  if (motivo === 'Dolor de cabeza fuerte hoy') return 'Hoy tienes dolor de cabeza fuerte, cuidaremos tu rutina.'
  if (motivo === 'Mareo hoy') return 'Hoy te sientes mareado/a, cuidaremos tu rutina.'
  return motivo
}

export const TITULO_SEMAFORO: Record<Semaforo, string> = {
  verde: 'Verde · ¡A entrenar!',
  amarillo: 'Amarillo · Entrena con cuidado',
  rojo: 'Rojo · Necesitas apto médico para entrenar hoy',
}

export const SUBTITULO_SEMAFORO: Record<Semaforo, string> = {
  verde: 'Todo está en orden. Armamos tu rutina.',
  amarillo: 'Tu coach revisará tu rutina.',
  rojo: 'Por tu seguridad, hoy no puedes entrenar. Habla con el personal.',
}
