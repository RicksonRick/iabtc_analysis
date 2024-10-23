from webhook import router
from fastapi import FastAPI, HTTPException, Header, APIRouter

app = FastAPI(
    title="GPT analista API",
    description="""
    API para configurar webhook para receber analises do GPT
    """,
    version="1.0.0",
)

app.include_router(router, prefix="/v1", tags=["webhook"])

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "OK"}