import { useCallback } from 'react'
import { ErrorBoundary } from './componentes/ErrorBoundary'
import { ProveedorFlujo, useFlujo } from './estado/flujo'
import { useInactividad } from './hooks'
import { Identificacion } from './pantallas/Identificacion'
import { Medicion } from './pantallas/Medicion'
import { Rutina } from './pantallas/Rutina'
import { Salud } from './pantallas/Salud'
import { PantallaSemaforo } from './pantallas/Semaforo'
import { Ticket } from './pantallas/Ticket'

export const INACTIVIDAD_MS = 60_000

function Pantallas() {
  const { estado, reiniciar } = useFlujo()
  // 60 s sin tocar: vuelve al inicio y borra los datos del socio de la memoria
  const expirar = useCallback(() => reiniciar(), [reiniciar])
  useInactividad(INACTIVIDAD_MS, expirar, estado.pantalla !== 'identificacion')

  switch (estado.pantalla) {
    case 'identificacion':
      return <Identificacion />
    case 'medicion':
      return <Medicion />
    case 'salud':
      return <Salud />
    case 'semaforo':
      return <PantallaSemaforo />
    case 'rutina':
      return <Rutina />
    case 'ticket':
      return <Ticket />
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <ProveedorFlujo>
        <Pantallas />
      </ProveedorFlujo>
    </ErrorBoundary>
  )
}
