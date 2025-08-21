# API ANIKI

API REST para acceder a información de animes y mangas, incluyendo filtros, detalles, imágenes, capítulos y búsqueda avanzada.

---

## Despliegue

La API está desplegada en:  
**https://api-aniki.onrender.com/**

---

## Uso con Docker

Puedes levantar la API localmente usando Docker:

```bash
docker build -t api-aniki .
docker run -p 8000:8000 api-aniki
```

Esto expondrá la API en `http://localhost:8000/`.

---

## Estructura de rutas (`main.py`)

Las rutas principales se incluyen así en `main.py`:

```python
# ...existing code...
app.include_router(animes.router, prefix="/api/animes")
app.include_router(animeschedule.router, prefix="/api")
app.include_router(animefilters.router, prefix="/api")
app.include_router(mangas.router, prefix="/api/mangas")
app.include_router(mangadetails.router, prefix="/api/mangas")
app.include_router(mangaimages.router, prefix="/api/mangas")
app.include_router(mangasearch.router, prefix="/api/mangas")
app.include_router(mangafilters.router, prefix="/api/mangas")
# ...existing code...
```

---

## Endpoints principales

### Animes

- **GET `/api/animes`**  
  Listado de animes filtrados.  
  **Ejemplo:**  
  ```
  GET /api/animes?category=tv-anime&genre=accion&page=1
  ```

- **GET `/api/animes/home`**  
  Home con animes destacados y últimos episodios.  
  **Ejemplo:**  
  ```
  GET /api/animes/home
  ```

- **GET `/api/animes/{slug}`**  
  Detalles de un anime.  
  **Ejemplo:**  
  ```
  GET /api/animes/one-piece
  ```

- **GET `/api/animes/{slug}/{number}`**  
  Detalles de un episodio.  
  **Ejemplo:**  
  ```
  GET /api/animes/one-piece/1
  ```

- **GET `/api/horario`**  
  Horario semanal de emisión.  
  **Ejemplo:**  
  ```
  GET /api/horario
  ```

- **GET `/api/filters`**  
  Opciones válidas para filtros de animes.  
  **Ejemplo:**  
  ```
  GET /api/filters
  ```

---

### Mangas

- **GET `/api/mangas/home`**  
  Resumen de mangas destacados y últimos añadidos.  
  **Ejemplo:**  
  ```
  GET /api/mangas/home
  ```

- **GET `/api/mangas/filters`**  
  Opciones válidas para filtros de mangas.  
  **Ejemplo:**  
  ```
  GET /api/mangas/filters
  ```

- **GET `/api/mangas/search`**  
  Búsqueda avanzada de mangas.  
  **Ejemplo:**  
  ```
  GET /api/mangas/search?title=Solo Leveling&page=1
  ```

- **GET `/api/mangas/detalle?url=...`**  
  Detalles completos de un manga.  
  **Ejemplo:**  
  ```
  GET /api/mangas/detalle?url=https://www.zonatmo.com/manga/solo-leveling
  ```

- **GET `/api/mangas/resolve_chapter?upload_url=...`**  
  Resuelve la URL de un capítulo.  
  **Ejemplo:**  
  ```
  GET /api/mangas/resolve_chapter?upload_url=https://www.zonatmo.com/viewer/12345
  ```

- **POST `/api/mangas/scrape-manga`**  
  Extrae imágenes de un capítulo manga.  
  **Ejemplo:**  
  ```json
  POST /api/mangas/scrape-manga
  {
    "url": "https://www.zonatmo.com/viewer/12345"
  }
  ```

---

## Respuestas

- Todas las respuestas son en formato JSON.
- Los endpoints de imágenes devuelven el binario de la imagen.
- Los errores siguen el estándar HTTP.

---

## Referencias

- [Render.com](https://dashboard.render.com/)
- [FastAPI](https://fastapi.tiangolo.com/)

---
