# 🍽️ Sazón — Demo de Base de Datos (Restaurante) · versión PYTHON

Página web + API para la **demo en vivo** del curso de Base de Datos.
Hecho con **PostgreSQL + Python (Flask) + HTML/CSS/JS**.

> La idea: abres la página, haces clic, y **abajo siempre se ve la consulta SQL exacta que se ejecutó** (panel oscuro "Consola SQL"). Así la profesora ve el SQL puro corriendo en vivo, sin diapositivas.

---

## 🚀 Cómo correrlo (paso a paso)

Necesitas **Python 3.10+** y **PostgreSQL** instalados en tu compu.

### 1. (Recomendado) Crear un entorno virtual e instalar librerías
Abre una terminal **dentro de la carpeta `restaurante-app-python`**:
```bash
# crear y activar el entorno virtual
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# instalar las librerías
pip install -r requirements.txt
```
> Si no quieres usar entorno virtual, simplemente corre `pip install -r requirements.txt` directo.

### 2. Crear la base de datos vacía en PostgreSQL
```bash
psql -U postgres -c "CREATE DATABASE restaurante;"
```

### 3. Configurar la conexión (.env)
Copia `.env.example` a `.env` y pon **tu** usuario y contraseña de postgres:
```bash
# Windows:  copy .env.example .env
# Mac/Linux:
cp .env.example .env
```
Edita `.env` (cambia `postgres:postgres` por **tu_usuario:tu_clave** si son distintos):
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/restaurante
PORT=3000
```

### 4. Crear las tablas y cargar datos de ejemplo
```bash
python init_db.py
```
Debe mostrar `Ejecutando 01_schema.sql ... OK`, etc., y al final **"Base de datos lista."**

### 5. Prender la página
```bash
python app.py
```
Abre el navegador en 👉 **http://localhost:3000**

¡Listo!

---

## ⚠️ ¿Por qué antes “no se guardaban los menús” / la página quedaba estática?

Casi siempre es **una de estas dos** (ya quedó más a prueba de errores, pero ojo):

1. **Abriste el `index.html` con doble clic** (la barra del navegador dice `file:///...`).
   Así la página **no tiene servidor detrás**, entonces no puede guardar nada y se queda
   estática. ✅ **Solución:** entra **siempre** por `http://localhost:3000`, no abriendo el archivo.

2. **El servidor estaba apagado** o **no corriste `python init_db.py`**, entonces la base
   no tenía las tablas y el guardado fallaba en silencio.
   ✅ **Solución:** deja la terminal con `python app.py` **abierta** mientras usas la página,
   y asegúrate de haber corrido el paso 4.

Ahora, si algo de eso pasa, la página ya **no se queda muda**: muestra un mensaje de error
explicando qué revisar (antes fallaba sin avisar nada, por eso parecía que “no guardaba”).

---

## ☁️ ¿Y lo de Supabase?

**No necesitas darme permisos de nada.** El proyecto corre 100% local (que es lo que pide la profe).

Si **además** lo quieres en Supabase, solo cambias **1 línea** en el `.env`: pones el `DATABASE_URL` que te da Supabase (Project Settings → Database → Connection string). El código le agrega `sslmode=require` solo. No tocas nada más. **Para la demo te recomiendo local** (más rápido, no dependes del internet del salón).

---

## 📁 Qué es cada archivo

```
restaurante-app-python/
│
├── db/                  ← TODO el SQL (esto es lo que la profe va a revisar)
│   ├── 01_schema.sql    ← crea las tablas + constraints (CHECK, UNIQUE, etc.)
│   ├── 02_seed.sql      ← datos de ejemplo
│   ├── 03_indices.sql   ← los índices (optimización)
│   └── consultas.sql    ← 📌 CHULETA: cada query y DÓNDE se usa (¡léela!)
│
├── public/              ← la página web (lo que se ve en el navegador)
│   ├── index.html
│   ├── styles.css
│   └── app.js
│
├── app.py               ← la API en Python (Flask): aquí están los endpoints
├── init_db.py           ← carga el SQL en la base ("python init_db.py")
├── requirements.txt     ← librerías de Python (Flask, psycopg2, etc.)
├── .env                 ← tu conexión a la base (lo creas tú en el paso 3)
├── .env.example         ← ejemplo del .env
└── README.md            ← este archivo
```

---

## 🗺️ Mapa: Rúbrica → dónde está → qué SQL corre

| Punto de la rúbrica | Pestaña | Endpoint | SQL clave |
|---|---|---|---|
| **Integridad y Constraints (2.0)** | "1. CRUD + Constraints" | `POST /api/productos` | `INSERT` que dispara `CHECK`, `UNIQUE`, `NOT NULL` |
| **CRUD Complejo 3+ tablas (4.0)** | "2. Pedido" | `POST /api/pedidos` | `INSERT` en `pedidos` + `detalle_pedido` + `UPDATE productos` |
| **Transacciones ACID (1.0)** | "2. Pedido" | `POST /api/pedidos` | `BEGIN ... COMMIT` / `ROLLBACK` si falta stock |
| **Reportes + Exportación (2.0)** | "3. Reportes" | `GET /api/reportes/ventas-por-categoria` | `GROUP BY` + `HAVING` + `JOIN` 4 tablas → CSV/JSON/Excel |
| **NoSQL / Híbrido (2.5)** | "4. NoSQL / JSONB" | `GET /api/nosql/buscar` | `WHERE atributos @> '{...}'::jsonb` |
| **Optimización / Índices (3.0)** | "5. Optimización" | `GET /api/optimizacion/explain` | `EXPLAIN ANALYZE` + índices (incluye GIN) |

> 📌 El detalle de **cada** consulta y dónde se usa está en **`db/consultas.sql`**.

---

## 🧩 ¿Por qué JSONB para el módulo híbrido? (lo que tienes que explicar)

La columna **`productos.atributos`** es **JSONB**: guarda atributos que **cambian de un producto a otro** (una bebida tiene `{"vegano": true, "calorias": 90}`, un plato tiene `{"picante": true, "alergenos": ["gluten"]}`).

**Ventaja sobre el modelo relacional:** si usáramos columnas normales, habría **una columna por atributo** (vegano, picante, calorías, alérgenos…) y casi todas quedarían en `NULL`, y cada atributo nuevo obligaría a un `ALTER TABLE`. Con JSONB cada producto guarda **solo lo que le aplica**, sin cambiar el esquema, y el **índice GIN** mantiene rápidas las búsquedas tipo "dame los veganos". **Tabla afectada: solo `productos`** → lo estructurado (precio, stock) queda relacional y lo flexible (atributos) queda en JSONB, en la misma tabla.

---

## ⏱️ Chuleta para los 15 minutos de demo

**[0:00–6:00] CRUD + Constraints** — pestaña "1. CRUD + Constraints"
1. Crear un plato nuevo → aparece en la lista.
2. Provocar el **error** a propósito: precio negativo (`CHECK`) o nombre repetido (`UNIQUE`).
3. **Editar** ese plato. 4. **Eliminar** ese plato.

**[6:00–9:00] Reportes** — pestaña "3. Reportes"
1. Mostrar el query `GROUP BY` + `HAVING` + `JOIN` de 4 tablas.
2. Botón **Ver JSON**, luego **Descargar CSV** y **Descargar Excel**.

**[9:00–12:00] Módulo híbrido NoSQL** — pestaña "4. NoSQL / JSONB"
1. Buscar `vegano = true`, o por alérgeno `gluten`.
2. Explicar tabla afectada (`productos`) y **por qué** JSONB.

**[12:00–15:00] Cada integrante** dice qué parte le costó más.
> Ideas: la **transacción** del pedido (que el `ROLLBACK` devuelva el stock), el **JOIN de 4 tablas**, o el **índice GIN** sobre JSONB.

**Bonus (optimización)** — pestaña "5. Optimización": correr `EXPLAIN ANALYZE` y mostrar los índices.

---

## 🛠️ Si algo falla

- **`password authentication failed`** → revisa usuario/clave en `.env`.
- **`database "restaurante" does not exist`** → te faltó el paso 2 (`CREATE DATABASE`).
- **`ModuleNotFoundError: No module named 'flask'`** → te faltó `pip install -r requirements.txt` (y activar el venv si lo usas).
- **La página abre pero las tablas están vacías** → corre `python init_db.py`.
- **`Address already in use` (puerto 3000)** → cambia `PORT=3000` a `PORT=3001` en `.env`.
- **Volver a empezar de cero** → corre otra vez `python init_db.py` (borra y recrea todo).

---

¡Éxitos en la demo! 🚀
