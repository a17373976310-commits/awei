from fastapi import FastAPI, UploadFile, Form, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
from .services.banana_service import banana_service
from .services.prompt_service import prompt_service

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
# In production, we serve the 'dist' folder built by Vite
# We check if 'dist' exists, otherwise fallback to 'frontend' (for local dev)
dist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dist")
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

if os.path.exists(dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_path, "assets")), name="assets")
    # Mount other static assets if needed, or just root for index.html
    
    @app.get("/")
    async def read_root():
        return FileResponse(os.path.join(dist_path, "index.html"))
    
    # Catch-all for SPA routing if needed, or just serve index.html
else:
    # Fallback for local development (serving raw source)
    app.mount("/frontend", StaticFiles(directory=frontend_path), name="frontend")
    
    @app.get("/")
    async def read_root():
        return FileResponse(os.path.join(frontend_path, "index.html"))

@app.post("/api/generate")
async def generate(
    prompt: str = Form(...),
    ratio: str = Form(...),
    scenario: str = Form("general"),
    model: str = Form("nano_banana_2"),
    api_key: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    mask: Optional[UploadFile] = File(None)
):
    try:
        image_bytes = await image.read() if image else None
        mask_bytes = await mask.read() if mask else None
        
        # Optimize prompt based on scenario
        # Pass image_bytes for multimodal understanding (LLM)
        final_prompt = prompt_service.optimize_prompt(prompt, scenario, image_bytes, api_key)
        
        result = banana_service.generate_image(final_prompt, ratio, image_bytes, mask_bytes, model, api_key)
        
        # If result is a URL, download it and convert to base64 (Proxy for China access)
        if result and result.startswith("http"):
            try:
                import requests
                import base64
                print(f"Proxying image from URL: {result}")
                img_response = requests.get(result)
                img_response.raise_for_status()
                b64_data = base64.b64encode(img_response.content).decode('utf-8')
                result = f"data:image/png;base64,{b64_data}"
            except Exception as proxy_error:
                print(f"Failed to proxy image: {proxy_error}")
                # Fallback to original URL if proxy fails
                pass

        # If result is raw base64 (no prefix), ensure it has prefix
        if result and not result.startswith("http") and not result.startswith("data:"):
            result = f"data:image/png;base64,{result}"
            
        return JSONResponse({
            "url": result,
            "optimized_prompt": final_prompt,
            "original_prompt": prompt
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8080, reload=True)
