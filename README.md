# Mis Finanzas

Dashboard web de finanzas personales: registra ingresos y gastos, filtra por periodo y entidad, y revisa en un vistazo cuánto ahorras.

Es una sola página estática (HTML + React + Recharts), sin servidor ni base de datos. Los datos se guardan en el navegador (`localStorage`).

## Funciones

- **Indicadores principales:** Ingresos, Gastos, Ahorros y Porcentaje de ahorro, en soles y dólares.
  - Ahorros = Ingresos − Gastos
  - Porcentaje de ahorro = Ahorros ÷ Ingresos × 100
  - Si los gastos superan a los ingresos se marca como *Déficit*.
- **Filtros** por año, mes, tipo, entidad financiera y método de pago.
- **Gráficos:** distribución de gastos por categoría (con categoría, monto y porcentaje al pasar el cursor) y gastos por método de pago, filtrable por entidad.
- **Tabla de registros** ordenable de mayor a menor (y viceversa) por cualquier columna, también con teclado.
- **Historial** con búsqueda, orden y paginación; **análisis por categorías**.
- **Registro de movimientos** con validación, edición y eliminación.
- **Importar y exportar CSV / respaldo JSON.**
- Tema claro y oscuro.

## Diseño

Paleta azul marino, tipografía IBM Plex Sans, estilo minimalista. Accesibilidad: foco visible, controles con `aria-pressed`, el estado de déficit no depende solo del color y se respeta `prefers-reduced-motion`.

## Uso

Abre `index.html` en el navegador o despliega la carpeta como sitio estático (Vercel, GitHub Pages, etc.). Se necesita conexión a internet para cargar React, Recharts y la tipografía desde CDN.

## Estructura

| Archivo | Descripción |
|---|---|
| `index.html` | Aplicación completa |
| `FinanzasPersonalesPC` | Misma aplicación (copia con el nombre original) |

## Flujo de ramas

- `main`: versión oficial publicada.
- `mejoras-dashboard`: pruebas y mejoras; se copia a `main` al terminar.

## Privacidad

Los movimientos incluidos en el código se cargan solo si el navegador no tiene datos guardados. Lo que registres después permanece en tu navegador.
