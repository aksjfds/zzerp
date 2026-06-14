from fastapi import FastAPI

app = FastAPI(title="zzerp")

@app.get("/")
def root():
    return {"message": "zzerp backend running"}