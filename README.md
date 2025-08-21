# api-aniki

API REST para acceder a información de animes y mangas, incluyendo filtros, detalles, imágenes, capítulos y búsqueda avanzada. Ideal para aplicaciones, bots o IA que requieran consumir datos de anime/manga desde un backend centralizado.

---

## URL Base

La API debe estar desplegada en un servidor FastAPI (por ejemplo, Render.com). Supón que la URL base es:

```
https://api-aniki.onrender.com
```

Todos los endpoints están bajo el prefijo `/api`.

---

## Endpoints principales

### Animes

- **GET `/api/animes`**  
  Listado de animes con filtros avanzados.
  - Parámetros (query):
    - `category`: lista, categorías válidas (`tv-anime`, `pelicula`, `ova`, `especial`)
    - `genre`: lista, géneros válidos (`accion`, `aventura`, etc.)
    - `min_year`, `max_year`: año de emisión
    - `status`: estado (`emision`, `finalizado`, `proximamente`)
    - `order`: orden (`predeterminado`, `popular`, etc.)
    - `letter`: letra inicial
    - `page`: número de página

  **Ejemplo:**
  ```
  GET /api/animes?category=tv-anime&genre=accion&order=popular&page=1
  ```

- **GET `/api/animes/home`**  
  Datos destacados de la home: animes destacados, últimos episodios y últimos añadidos.

- **GET `/api/animes/{slug}`**  
  Detalles completos de un anime por su slug.

- **GET `/api/animes/{slug}/{number}`**  
  Detalles y enlaces de un episodio específico.

- **GET `/api/horario`**  
  Horario semanal de emisión de animes.

- **GET `/api/filters`**  
  Opciones válidas para filtros de animes.

---

### Mangas

- **GET `/api/mangas/home`**  
  Resumen completo de mangas: populares, trending, últimos añadidos, subidas, top semanal/mensual.

- **GET `/api/mangas/filters`**  
  Opciones válidas para filtros de mangas.

- **GET `/api/mangas/search`**  
  Búsqueda avanzada de mangas con múltiples filtros.
  - Parámetros (query):
    - `title`, `order_item`, `order_dir`, `type`, `demography`, `status`, `translation_status`, `webcomic`, `yonkoma`, `amateur`, `erotic`, `genres`, `exclude_genres`, `page`, `filter_by`

  **Ejemplo:**
  ```
  GET /api/mangas/search?title=Solo Leveling&type=manhwa&order_item=score&order_dir=desc&page=1
  ```

- **GET `/api/mangas/detalle?url=...`**  
  Detalles completos de una obra manga (requiere URL de ZonaTMO).

- **GET `/api/mangas/resolve_chapter?upload_url=...`**  
  Resuelve la URL de un capítulo a su forma final de visualización.

- **POST `/api/mangas/scrape-manga`**  
  Extrae imágenes de un capítulo manga (requiere URL de viewer de ZonaTMO).
  - Body JSON: `{ "url": "<url del capítulo>" }`

- **GET `/api/mangas/scrape-manga/viewer/{chapter_title}/{uuid}`**  
  Visor HTML para las imágenes extraídas de un capítulo.

- **GET `/api/mangas/scrape-manga/image/{viewer_id}/{page_number}/{filename}`**  
  Proxy para obtener imágenes individuales de un capítulo.

---

## Ejemplo de consumo (Python)

```python
import requests

# Listar animes filtrados
resp = requests.get("https://api-aniki.onrender.com/api/animes", params={
    "category": "tv-anime",
    "genre": "accion",
    "order": "popular",
    "page": 1
})
print(resp.json())

# Buscar mangas
resp = requests.get("https://api-aniki.onrender.com/api/mangas/search", params={
    "title": "Solo Leveling",
    "type": "manhwa",
    "order_item": "score",
    "order_dir": "desc",
    "page": 1
})
print(resp.json())
```

---

## Filtros y opciones válidas

Consulta `/api/filters` y `/api/mangas/filters` para obtener las opciones válidas de cada filtro (géneros, categorías, estados, orden, etc.).

---

## Respuestas y formato

- Todas las respuestas son en formato JSON.
- Los errores siguen el estándar HTTP (400, 404, 500, etc.).
- Los endpoints de imágenes devuelven directamente el binario de la imagen.

---

## Uso para IA y desarrolladores

- La API está pensada para ser consumida por cualquier cliente HTTP.
- Los endpoints permiten obtener datos estructurados para construir aplicaciones, bots, o sistemas de recomendación.
- Los filtros permiten búsquedas avanzadas y personalizadas.


## Recomendaciones para IA y desarrolladores

- La API sigue convenciones REST, por lo que puedes interactuar con ella usando cualquier cliente HTTP.
- Los datos se envían y reciben en formato JSON.
- Para construir aplicaciones basadas en esta API, simplemente realiza peticiones HTTP a los endpoints documentados.
- Si necesitas endpoints adicionales, revisa el código fuente o consulta la documentación interna del proyecto.

---

## Referencias

- [Render.com](https://dashboard.render.com/)
- [Documentación REST](https://restfulapi.net/)

---
