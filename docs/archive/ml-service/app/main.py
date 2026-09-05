from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Security Intelligence ML/AI Microservice",
    description="Microservice providing anomaly detection, RAG assistant pipeline, and event correlation.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ml-service"}

@app.get("/")
def root():
    return {"message": "Security Intelligence ML Service Active"}
