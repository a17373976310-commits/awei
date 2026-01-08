import os
import json
import base64
import time
import requests
from typing import Optional
from fastapi import FastAPI, UploadFile, Form, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from services.banana_service import banana_service
from services.prompt_service import prompt_service
from services.task_service import task_service

def debug_log(message: str):
    """Helper to log debug info to a file since terminal output might be truncated or hard to follow."""
    try:
        log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debug.log")
        with open(log_path, "a", encoding="utf-8") as f:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except:
        pass

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
dist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dist")
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

# Ensure static directory exists
os.makedirs(static_path, exist_ok=True)
os.makedirs(os.path.join(static_path, "history"), exist_ok=True)

# Mount static folder for history and other assets
app.mount("/static", StaticFiles(directory=static_path), name="static")

if os.path.exists(dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_path, "assets")), name="assets")
    
    @app.get("/")
    async def read_root():
        return FileResponse(os.path.join(dist_path, "index.html"))
else:
    # Fallback for local development
    app.mount("/frontend", StaticFiles(directory=frontend_path), name="frontend")
    
    @app.get("/")
    async def read_root():
        return FileResponse(os.path.join(frontend_path, "index.html"))

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    task = task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/api/generate")
async def generate(
    background_tasks: BackgroundTasks,
    prompt: str = Form(...),
    ratio: str = Form(...),
    scenario: str = Form("general"),
    model: str = Form("nano_banana_2"),
    api_key: Optional[str] = Form(None),
    api_url: Optional[str] = Form(None),
    image: Optional[list[UploadFile]] = File(None),
    mask: Optional[UploadFile] = File(None)
):
    task_id = task_service.create_task("image_generation")
    
    # Read files immediately before background task
    image_bytes_list = []
    if image:
        for img in image:
            content = await img.read()
            if content:
                image_bytes_list.append(content)
    
    mask_bytes = await mask.read() if mask else None
    
    background_tasks.add_task(
        run_generation_task,
        task_id, prompt, ratio, scenario, model, api_key, api_url, image_bytes_list, mask_bytes
    )
    
    return {"task_id": task_id, "status": "pending"}

async def run_generation_task(
    task_id: str,
    prompt: str,
    ratio: str,
    scenario: str,
    model: str,
    api_key: Optional[str],
    api_url: Optional[str],
    image_bytes_list: list[bytes],
    mask_bytes: Optional[bytes]
):
    try:
        task_service.update_task(task_id, status="processing", progress=5, progress_message="🎬 初始化生成任务...")
        print(f"\n>>> [ASYNC TASK {task_id}] Prompt: {prompt[:50]}... | Model: {model}")
        
        # 1. Optimize prompt
        if image_bytes_list:
            task_service.update_task(task_id, progress=10, progress_message=f"📸 分析上传的 {len(image_bytes_list)} 张产品图...")
        
        task_service.update_task(task_id, progress=15, progress_message="🤖 准备提示词优化引擎...")
        try:
            optimized_result = prompt_service.optimize_prompt(prompt, scenario, image_bytes_list, api_key, api_url, task_id, task_service)
            task_service.update_task(task_id, progress=30, progress_message="✨ 提示词优化完成")
        except Exception as e:
            print(f"Prompt optimization failed: {e}")
            task_service.update_task(task_id, progress=30, progress_message="⚠️ 提示词优化失败,使用原始提示词")
            optimized_result = prompt # Fallback to original prompt
        
        final_prompt = optimized_result
        layout_logic = ""
        
        try:
            import json
            prompt_data = json.loads(optimized_result)
            
            # Handle Luxury Visual Strategy format
            if "luxury_visual_strategy" in prompt_data:
                strategy = prompt_data["luxury_visual_strategy"]
                screens = strategy.get("screens", [])
                if screens:
                    # Default to the first screen (Brand Impact)
                    first_screen = screens[0]
                    final_prompt = first_screen.get("positive_prompt", optimized_result)
                    layout_logic = f"Screen: {first_screen.get('screen_name_zh', '1')}\n{strategy.get('visual_grammar_handbook', {}).get('composition_rules', {})}"
                else:
                    final_prompt = optimized_result
            else:
                # Standard Dual-Core format
                is_seadream = "doubao" in model.lower() or "seadream" in model.lower()
                if is_seadream:
                    final_prompt = prompt_data.get("seadream_cn", prompt_data.get("nano_banana_en", optimized_result))
                else:
                    final_prompt = prompt_data.get("nano_banana_en", prompt_data.get("seadream_cn", optimized_result))
                layout_logic = prompt_data.get("layout_logic", "")
        except Exception as e:
            print(f"DEBUG_LOG: JSON parsing failed or format mismatch: {e}")
            final_prompt = optimized_result

        task_service.update_task(task_id, progress=35, progress_message="🔧 准备图像生成参数...")
        # 2. Generate Image
        from models import get_model_info
        model_info = get_model_info(model)
        model_display_name = model_info.get("name", model) if model_info else model
        provider = model_info.get("provider", "default") if model_info else "default"
        primary_image = image_bytes_list[0] if image_bytes_list else None
        
        # More detailed progress based on whether it's text-to-image or image-to-image
        if primary_image:
            task_service.update_task(task_id, progress=40, progress_message=f"🖌️ 正在使用 {model_display_name} 进行图像编辑...")
        else:
            task_service.update_task(task_id, progress=40, progress_message=f"🎨 正在使用 {model_display_name} 生成图像...")
        
        task_service.update_task(task_id, progress=45, progress_message=f"📡 正在发送请求到 {provider} 服务器...")
        
        try:
            result = banana_service.generate_image(final_prompt, ratio, primary_image, mask_bytes, model, api_key, api_url)
            task_service.update_task(task_id, progress=70, progress_message="🖼️ 图像生成完成,正在处理...")
        except Exception as e:
            error_msg = str(e)
            if "Remote end closed connection" in error_msg or "Connection aborted" in error_msg:
                error_msg = "与生成服务器连接中断，请稍后重试。"
            elif "timeout" in error_msg.lower():
                error_msg = "生成超时，请尝试缩短提示词或稍后再试。"
            raise Exception(error_msg)

        if not result:
            raise Exception("生成服务器未返回有效图像，请检查 API Key 或余额。")

        debug_log(f"Task {task_id}: Generation result type: {type(result)}")
        if isinstance(result, str):
            debug_log(f"Task {task_id}: Result prefix: {result[:50]}...")
        
        # 3. Proxy image (Download and convert to Base64)
        if result and isinstance(result, str) and result.startswith("http"):
            task_service.update_task(task_id, progress=80, progress_message="📥 正在下载生成的图像...")
            try:
                # Retry download up to 2 times
                for attempt in range(2):
                    try:
                        # Bypass proxies to avoid connection issues
                        img_response = requests.get(result, timeout=30, proxies={"http": None, "https": None})
                        img_response.raise_for_status()
                        b64_data = base64.b64encode(img_response.content).decode('utf-8')
                        result = f"data:image/png;base64,{b64_data}"
                        break
                    except Exception as download_err:
                        print(f"Proxy download attempt {attempt+1} failed: {download_err}")
                        if attempt == 0: time.sleep(2)
            except Exception as e:
                print(f"Proxy failed completely: {e}")
                # Keep original URL if proxy fails

        if result and isinstance(result, str):
            result = result.strip()
            if not result.startswith("http") and not result.startswith("data:"):
                result = f"data:image/png;base64,{result}"
            
        # 4. Save History
        task_service.update_task(task_id, progress=85, progress_message="💾 正在保存到历史记录...")
        try:
            timestamp = int(time.time() * 1000)
            history_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "history")
            os.makedirs(history_dir, exist_ok=True)

            # Save generated image
            saved_image = False
            if result:
                if result.startswith("data:image"):
                    try:
                        header, encoded = result.split(",", 1)
                        img_data = base64.b64decode(encoded)
                        save_path = os.path.join(history_dir, f"{timestamp}.png")
                        with open(save_path, "wb") as f:
                            f.write(img_data)
                        saved_image = True
                        debug_log(f"Task {task_id}: Saved base64 image to {save_path}")
                    except Exception as e:
                        debug_log(f"Task {task_id}: Error saving base64 image: {e}")
                elif result.startswith("http"):
                    try:
                        # Download the image if it's a URL
                        debug_log(f"Task {task_id}: Downloading image from {result}")
                        img_response = requests.get(result, timeout=30, proxies={"http": None, "https": None})
                        img_response.raise_for_status()
                        save_path = os.path.join(history_dir, f"{timestamp}.png")
                        with open(save_path, "wb") as f:
                            f.write(img_response.content)
                        saved_image = True
                        debug_log(f"Task {task_id}: Downloaded and saved image to {save_path}")
                    except Exception as e:
                        debug_log(f"Task {task_id}: Error downloading image for history: {e}")
                else:
                    debug_log(f"Task {task_id}: Result format not recognized for saving: {result[:50]}...")

            if not saved_image:
                debug_log(f"Task {task_id}: Warning: Generated image was not saved to history")

            # Save original images and collect their relative URLs
            original_images_urls = []
            for idx, img_bytes in enumerate(image_bytes_list):
                orig_filename = f"{timestamp}_orig_{idx}.jpg"
                with open(os.path.join(history_dir, orig_filename), "wb") as f:
                    f.write(img_bytes)
                original_images_urls.append(f"/static/history/{orig_filename}")
            
            print(f"DEBUG_LOG: Saved {len(image_bytes_list)} original images")

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
            
            print(f"History saved successfully for timestamp: {timestamp}")
        except Exception as e:
            print(f"History save error: {e}")

        task_service.update_task(task_id, status="succeed", progress=100, progress_message="✅ 完成!", result={
            "id": str(timestamp),
            "url": f"/static/history/{timestamp}.png" if saved_image else result,
            "optimized_prompt": final_prompt,
            "original_prompt": prompt,
            "original_images": original_images_urls,
            "timestamp": timestamp
        })
        debug_log(f"Task {task_id}: Success. Result URL: {f'/static/history/{timestamp}.png' if saved_image else result}")
        print(f"<<< [ASYNC TASK {task_id} SUCCESS] Result URL: {f'/static/history/{timestamp}.png' if saved_image else result}")

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"ASYNC TASK ERROR: {str(e)}\n{error_trace}")
        task_service.update_task(task_id, status="failed", error=str(e))

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Detect if running in production (Zeabur) or development
    is_production = os.getenv("ZEABUR_SERVICE_ID") is not None
    
    # Get port from environment variable (Zeabur sets PORT)
    port = int(os.getenv("PORT", 8080))
    
    if is_production:
        # Production mode: use backend.main:app and disable reload
        uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)
    else:
        # Development mode: use main:app (for running from backend directory) and enable reload
        uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
