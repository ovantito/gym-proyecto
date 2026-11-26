import { useState } from 'react'
import { Aviso } from '../componentes/Aviso'
import { Boton } from '../componentes/Boton'
import { Marco } from '../componentes/Marco'
import { Teclado } from '../componentes/Teclado'
import { useFlujo } from '../estado/flujo'

/** Pantalla 1. Sin lector real: se escribe el DNI en el teclado en pantalla y se "simula la lectura". */
export function Identificacion() {
  const { estado, identificar, limpiarError } = useFlujo()
  const [dni, setDni] = useState('')
  return (
    <Marco paso={1}>
      <div className="grid h-full grid-cols-2 items-center gap-16">
        <div>
          <h1 className="text-[64px] font-extrabold leading-[1.05]">Entrena seguro, sin celular.</h1>
          <p className="mt-5 text-[26px] text-suave">Mídete, revisa tu salud y recibe tu rutina en pocos minutos.</p>
          <div className="mt-10 rounded-3xl border-2 border-dashed border-naranja/60 bg-tarjeta p-8">
            <p className="text-[34px] font-bold">Acerca tu DNI o QR</p>
            <p className="mt-2 text-[20px] text-suave">El lector está debajo de la pantalla. Aquí puedes simularlo con tu DNI.</p>
          </div>
        </div>
        <div className="flex flex-col gap-4">
          <div
            aria-label="DNI"
            className="flex h-[84px] items-center justify-center rounded-2xl border-2 border-borde bg-tarjeta text-[48px] font-bold tracking-[0.3em]"
          >
            {dni ? dni : <span className="text-[24px] font-normal tracking-normal text-suave">Escribe tu DNI (8 dígitos)</span>}
          </div>
          <Teclado valor={dni} max={8} onCambio={setDni} />
          {estado.error && <Aviso onCerrar={limpiarError}>{estado.error}</Aviso>}
          <Boton disabled={dni.length !== 8 || estado.cargando} onClick={() => identificar(dni)}>
            {estado.cargando ? 'Buscando…' : 'Simular lectura'}
          </Boton>
        </div>
      </div>
    </Marco>
  )
}
