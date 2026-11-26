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

export const LESIONES = [
  { id: 'rodilla', texto: 'Rodilla' },
  { id: 'hombro', texto: 'Hombro' },
  { id: 'espalda_baja', texto: 'Espalda' },
] as const

/** "¿Cómo te sientes hoy?" se traduce a respuestas PAR-Q+ (el backend no tiene otro campo). */
export const ANIMOS = [
  { id: 'bien', texto: 'Bien', parq: null },
  { id: 'cansado', texto: 'Cansado/a', parq: null },
  { id: 'mareado', texto: 'Mareado/a', parq: 3 }, // pregunta 4 (mareos)
  { id: 'pecho', texto: 'Dolor en el pecho', parq: 1 }, // pregunta 2 (dolor de pecho al hacer actividad)
] as const

/** Convierte el motivo técnico del backend en palabras simples. */
export function motivoSimple(motivo: string): string {
  if (motivo.startsWith('Bloqueado')) return 'Un coach debe liberarte antes de entrenar.'
  if (motivo.startsWith('Presión')) return 'Tu presión está alta hoy.'
  if (motivo.startsWith('Pulso')) return 'Tu pulso en reposo está muy acelerado.'
  if (motivo.startsWith('PAR-Q+ con respuesta crítica')) return 'Una de tus respuestas sobre el corazón o el pecho necesita revisión médica.'
  if (motivo.startsWith('PAR-Q+')) return 'Marcaste una molestia en el cuestionario.'
  if (motivo.startsWith('Lesión declarada')) return `Por tu lesión de ${motivo.split(': ')[1] ?? 'tu cuerpo'}, cuidaremos tu rutina.`
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

export const MENSAJE_BLOQUEADO = 'Tu semáforo sigue en rojo. Acércate al coach para que te evalúe y te libere.'
