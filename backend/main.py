from fastapi import FastAPI, UploadFile, Form, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
from .services.banana_service import banana_service
from .services.prompt_service import prompt_service

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import json

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
    image: Optional[list[UploadFile]] = File(None),
    mask: Optional[UploadFile] = File(None)
):
    try:
        print(f"\n>>> [NEW REQUEST] Prompt: {prompt[:50]}... | Model: {model} | Ratio: {ratio}")
        
        image_bytes_list = []
        if image:
            for img in image:
                content = await img.read()
                if content:
                    image_bytes_list.append(content)
        
        mask_bytes = await mask.read() if mask else None
        
        # Optimize prompt based on scenario
        # Returns a JSON string with dual-core prompts
        optimized_result = prompt_service.optimize_prompt(prompt, scenario, image_bytes_list, api_key)
        
        final_prompt = optimized_result
        layout_logic = ""
        
        try:
            # Try to parse as JSON (Dual-Core Engine output)
            prompt_data = json.loads(optimized_result)
            
            # Select prompt based on model
            is_seadream = "doubao" in model.lower() or "seadream" in model.lower()
            
            if is_seadream:
                final_prompt = prompt_data.get("seadream_cn", optimized_result)
                print(f"DEBUG_LOG: Selected Chinese prompt for SeaDream/Doubao model.")
            else:
                final_prompt = prompt_data.get("nano_banana_en", optimized_result)
                print(f"DEBUG_LOG: Selected English prompt for Nano-Banana model.")
            
            layout_logic = prompt_data.get("layout_logic", "")
        except Exception as e:
            # Fallback if not JSON
            print(f"DEBUG_LOG: Optimized result is not JSON or parsing failed: {e}")
            final_prompt = optimized_result

        primary_image = image_bytes_list[0] if image_bytes_list else None
        result = banana_service.generate_image(final_prompt, ratio, primary_image, mask_bytes, model, api_key)
        
        # If result is a URL, download it and convert to base64 (Proxy for China access)
        if result and isinstance(result, str) and result.startswith("http"):
            try:
                import requests
                import base64
                print(f"Proxying image from URL: {result}")
                img_response = requests.get(result, timeout=20)
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
            
        # Convert all original images to base64 for history
        original_images_b64 = []
        for img_bytes in image_bytes_list:
            b64 = base64.b64encode(img_bytes).decode('utf-8')
            original_images_b64.append(f"data:image/jpeg;base64,{b64}")

        # --- Server-side History Saving ---
        try:
            import time
            timestamp = int(time.time() * 1000)
            history_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "history")
            os.makedirs(history_dir, exist_ok=True)

            # Save generated image
            if result and result.startswith("data:image"):
                header, encoded = result.split(",", 1)
                img_data = base64.b64decode(encoded)
                with open(os.path.join(history_dir, f"{timestamp}.png"), "wb") as f:
                    f.write(img_data)
                print(f"DEBUG_LOG: Saved generated image to {history_dir}/{timestamp}.png")

            # Save original images
            for idx, img_bytes in enumerate(image_bytes_list):
                with open(os.path.join(history_dir, f"{timestamp}_orig_{idx}.jpg"), "wb") as f:
                    f.write(img_bytes)
                print(f"DEBUG_LOG: Saved original image {idx} to {history_dir}/{timestamp}_orig_{idx}.jpg")

            # Save metadata
            metadata = {
                "timestamp": timestamp,
                "original_prompt": prompt,
                "optimized_prompt": final_prompt,
                "scenario": scenario,
                "model": model,
                "ratio": ratio,
                "layout_logic": layout_logic,
                "original_images_count": len(image_bytes_list)
            }
            with open(os.path.join(history_dir, f"{timestamp}.json"), "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            print(f"DEBUG_LOG: Saved metadata to {history_dir}/{timestamp}.json")
        except Exception as save_error:
            print(f"WARNING: Failed to save history to disk: {save_error}")
        # ----------------------------------

        print(f"<<< [SUCCESS] Image generated and processed.")
        return JSONResponse({
            "url": result,
            "optimized_prompt": final_prompt,
            "original_prompt": prompt,
            "original_images": original_images_b64
        })
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"CRITICAL_ERROR in /api/generate: {str(e)}\n{error_trace}")
        
        with open("backend_error.log", "a", encoding="utf-8") as f:
            import datetime
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{now}] CRITICAL_ERROR: {str(e)}\n{error_trace}\n")
            
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8080, reload=True)
