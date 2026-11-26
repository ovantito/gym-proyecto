import QRCode from 'qrcode'
import { useEffect, useState } from 'react'
import { obtenerVideo, type RutinaOut } from '../api/cliente'
import { Boton } from '../componentes/Boton'
import { Marco } from '../componentes/Marco'
import { useFlujo } from '../estado/flujo'

function TicketContenido({ rutina, nombre, qr }: { rutina: RutinaOut; nombre: string; qr: string | null }) {
  const ej = rutina.dias.flatMap((d) => d.ejercicios)
  const fecha = new Date().toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' })
  return (
    <div>
      <p className="font-bold">TNT FIT · SEDE 01</p>
      <p>{nombre}</p>
      <p>{fecha}</p>
      <p>--------------------------------</p>
      {ej.map((e, i) => (
        <p key={e.id}>
          {i + 1}. {e.maquina} {e.nombre} {e.series}x{e.repeticiones}
          <span className="hidden print:block">
            &nbsp;&nbsp;&nbsp;descanso {e.descansoSeg}s
          </span>
        </p>
      ))}
      <p>--------------------------------</p>
      <p className="font-bold">
        {rutina.estado === 'pendiente_aprobacion' ? 'PENDIENTE DE APROBACION DEL COACH' : 'RUTINA ACTIVA'}
      </p>
      {qr ? (
        <>
          <div dangerouslySetInnerHTML={{ __html: qr }} aria-label="Código QR" role="img" />
          <p>Escanea: video del 1er ejercicio (vence en 15 min)</p>
        </>
      ) : (
        <p>Videos no disponibles por ahora.</p>
      )}
    </div>
  )
}

/** Pantalla 6: ticket tipo 80 mm con QR al video del primer ejercicio. */
export function Ticket() {
  const { estado, reiniciar } = useFlujo()
  const [qr, setQr] = useState<string | null>(null)
  const rutina = estado.rutina
  const primero = rutina?.dias[0]?.ejercicios[0]?.id

  useEffect(() => {
    if (!primero) return
    let vivo = true
    obtenerVideo(primero)
      .then((v) => QRCode.toString(v.url, { type: 'svg', margin: 1, errorCorrectionLevel: 'L' }))
      .then((svg) => vivo && setQr(svg))
      .catch(() => vivo && setQr(null)) // sin video: el ticket sale igual, sin QR
    return () => {
      vivo = false
    }
  }, [primero])

  if (!rutina) return null
  const nombre = estado.socio?.nombre ?? ''
  return (
    <>
      <Marco
        paso={4}
        pie={
          <>
            <Boton variante="secundario" onClick={() => window.print()}>
              Imprimir
            </Boton>
            <Boton className="ml-auto" onClick={reiniciar}>
              Terminar
            </Boton>
          </>
        }
      >
        <div className="grid h-full grid-cols-[1fr_auto] items-center gap-16">
          <div>
            <div className="flex h-24 w-24 items-center justify-center rounded-full bg-teal text-[56px] font-bold text-fondo">✓</div>
            <h1 className="mt-6 text-[52px] font-extrabold">¡Recoge tu ticket!</h1>
            <p className="mt-3 text-[26px] text-suave">Busca cada máquina por su código y escanea el QR para ver los videos.</p>
          </div>
          <div className="w-[440px] rounded-xl bg-white p-5 font-mono text-[16px] leading-snug text-black shadow-2xl [&_svg]:h-32 [&_svg]:w-32">
            <TicketContenido rutina={rutina} nombre={nombre} qr={qr} />
          </div>
        </div>
      </Marco>
      <div className="ticket-impreso">
        <TicketContenido rutina={rutina} nombre={nombre} qr={qr} />
      </div>
    </>
  )
}
