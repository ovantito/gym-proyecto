/** Teclado numérico en pantalla (no hay teclado físico). */
export function Teclado({ valor, max, onCambio }: { valor: string; max: number; onCambio: (v: string) => void }) {
  const tecla = 'h-[84px] rounded-2xl bg-tarjeta2 text-[36px] font-bold border border-borde active:bg-borde'
  return (
    <div className="grid grid-cols-3 gap-3" aria-label="Teclado numérico">
      {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((d) => (
        <button key={d} type="button" className={tecla} onClick={() => valor.length < max && onCambio(valor + d)}>
          {d}
        </button>
      ))}
      <button type="button" className={`${tecla} text-[22px] text-suave`} onClick={() => onCambio('')}>
        Limpiar
      </button>
      <button type="button" className={tecla} onClick={() => valor.length < max && onCambio(valor + '0')}>
        0
      </button>
      <button type="button" aria-label="Borrar" className={tecla} onClick={() => onCambio(valor.slice(0, -1))}>
        ⌫
      </button>
    </div>
  )
}
