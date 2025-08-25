from fastapi import FastAPI
from routers import animefilters, animes, animeschedule, mangas, mangadetails, mangaimages, mangasearch, mangafilters

app = FastAPI(title="Anime & Manga API")

# Registrar routers
app.include_router(animes.router, prefix="/api/animes", tags=["Animes"])
app.include_router(animeschedule.router, prefix="/api", tags=["Animes Schedule"])
app.include_router(animefilters.router, prefix="/api", tags=["Animes Filters"])
app.include_router(mangas.router, prefix="/api/mangas", tags=["Mangas"]) 
app.include_router(mangadetails.router, prefix="/api/mangas", tags=["Manga Details"]) 
app.include_router(mangaimages.router, prefix="/api/mangas", tags=["Manga Images"])
app.include_router(mangasearch.router, prefix="/api/mangas", tags=["Manga Search"])
app.include_router(mangafilters.router, prefix="/api/mangas", tags=["Manga Filters"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)