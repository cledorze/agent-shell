from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

# Importation de la configuration et des composants
from config import initialize_components, setup_logging, frontend_dir
from routes import router

# Configuration du logging
logger = setup_logging()

# Initialisation des composants
command_generator, execution_engine, state_manager, llm_service = initialize_components()

# Initialisation de l'application FastAPI
app = FastAPI(title="Linux Agent System")

# Montage des fichiers statiques pour le frontend s'ils existent
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    logger.info(f"Mounted frontend directory: {frontend_dir}")

# Ajout des routes
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8082, reload=True)
