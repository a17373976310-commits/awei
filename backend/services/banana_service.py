import requests
import base64
from ..config import config
from ..models import MODEL_REGISTRY

# 1. 【强制尺寸映射】
SIZE_MAP = {
    "1:1":  {"width": 1024, "height": 1024},
    "4:3":  {"width": 1152, "height": 896},
    "3:4":  {"width": 896,  "height": 1152},
    "16:9": {"width": 1280, "height": 720},
    "9:16": {"width": 720,  "height": 1280}
}

OPENAI_SIZE_MAP = {
    "1:1": "1024x1024",
    "4:3": "1024x768",
    "3:4": "768x1024",
    "16:9": "1280x720",
    "9:16": "720x1280"
}

class BananaService:
    def generate_image(self, prompt: str, ratio: str, image: bytes = None, mask: bytes = None, model_id: str = "nano_banana_2", api_key: str = None):
        # Get model config
        model_config = MODEL_REGISTRY.get(model_id)
        if not model_config:
            # Fallback to default
            model_config = MODEL_REGISTRY["nano_banana_2"]
            
        # 2. 【重写参数处理逻辑】
        # 获取尺寸
        size_config = SIZE_MAP.get(ratio, SIZE_MAP["1:1"]) # Default to 1:1 if not found
        width = size_config["width"]
        height = size_config["height"]
        
        # 3. 【修复 Doubao 模型调用】
        # 确保使用配置中的真实 model_key
        real_model_id = model_config["model_key"]

        payload = {
            "prompt": prompt,
            "negative_prompt": "",
            "width": width,
            "height": height,
            "guidance_scale": 7.5,
            "num_inference_steps": 30,
            "model": real_model_id,
            "aspect_ratio": ratio
        }

        if image:
            payload["image"] = base64.b64encode(image).decode('utf-8')
            payload["strength"] = 0.7 
        
        if mask:
            payload["mask"] = base64.b64encode(mask).decode('utf-8')

        # Determine URL based on provider
        url = model_config["url"]
        if model_config.get("provider") == "comfly":
            if image:
                url = f"{url.rstrip('/')}/images/edits"
            else:
                url = f"{url.rstrip('/')}/images/generations"
            
        # Unified Parameter Logic:
        # Comfly/OpenAI/Banana usually expect 'size' string.
        payload["size"] = f"{width}x{height}"
            
        # Determine API Key
        final_api_key = api_key if api_key else config.BANANA_API_KEY
        if final_api_key:
            final_api_key = final_api_key.strip()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {final_api_key}"
        }

        # 4. 【添加调试日志】
        print(f"DEBUG_LOG: 用户选择={ratio}, 正在发送尺寸: {width} x {height}, 模型ID: {real_model_id}")
        print(f"DEBUG_PAYLOAD: {payload}")

        if image:
            # --- Image-to-Image (Multipart) ---
            url = f"{model_config['url'].rstrip('/')}/images/edits"
            
            # 1. Prepare Files
            files = {
                'image': ('image.png', image, 'image/png')
            }
            if mask:
                files['mask'] = ('mask.png', mask, 'image/png')
            
            # 2. Prepare Data (Parameters)
            # size_str = OPENAI_SIZE_MAP.get(ratio, "1024x1024") 
            # Google model requires aspect_ratio, not size string for edits apparently
            data = {
                "prompt": prompt,
                "model": real_model_id,
                "n": 1,
                "aspect_ratio": ratio,
                "response_format": "url"
            }
            
            # Remove Content-Type: application/json for multipart
            if "Content-Type" in headers:
                del headers["Content-Type"]
                
            print(f"DEBUG_LOG: Sending Multipart Request (Img2Img). URL={url}")
            print(f"DEBUG_DATA: {data}")
            response = requests.post(url, headers=headers, files=files, data=data)
            
        else:
            # --- Text-to-Image (JSON) ---
            # Clean parameters: Remove width/height/size, keep aspect_ratio
            if "width" in payload: del payload["width"]
            if "height" in payload: del payload["height"]
            if "size" in payload: del payload["size"]
            
            # Ensure aspect_ratio is present (it should be, but just in case)
            payload["aspect_ratio"] = ratio
            
            print(f"DEBUG_LOG: Sending JSON Request (Txt2Img). URL={url}")
            print(f"DEBUG_PAYLOAD_CLEANED: {payload}")
            response = requests.post(url, json=payload, headers=headers)

        try:
            response.raise_for_status()
            result = response.json()
            
            if "output" in result and len(result["output"]) > 0:
                 return result["output"][0] 
            
            if "data" in result and len(result["data"]) > 0:
                item = result["data"][0]
                if "url" in item:
                    return item["url"]
                if "b64_json" in item:
                    return item["b64_json"]

            return result.get("url", "")
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"API Error JSON: {error_detail}")
                    error_msg = f"{str(e)} - Detail: {error_detail}"
                except:
                    print(f"API Error Text: {e.response.text}")
                    error_msg = f"{str(e)} - Detail: {e.response.text}"
            
            # Log to file
            with open("backend_error.log", "a", encoding="utf-8") as f:
                f.write(f"Error: {error_msg}\n")
            
            print(f"Error generating image: {error_msg}")
            raise Exception(error_msg)

banana_service = BananaService()
