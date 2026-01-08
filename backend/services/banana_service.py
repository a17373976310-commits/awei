import requests
import base64
try:
    from config import config
    from models import MODEL_REGISTRY
except ImportError:
    from backend.config import config
    from backend.models import MODEL_REGISTRY

# 1. 【多级尺寸映射系统】
# 1K 标准版 (约 1MP)
SIZE_MAP_1K = {
    "1:1":  {"width": 1024, "height": 1024},
    "4:3":  {"width": 1152, "height": 896},
    "3:4":  {"width": 896,  "height": 1152},
    "16:9": {"width": 1280, "height": 720},
    "9:16": {"width": 720,  "height": 1280}
}

# 2K 高清版 (约 4MP)
SIZE_MAP_2K = {
    "1:1":  {"width": 2048, "height": 2048},
    "4:3":  {"width": 2304, "height": 1728},
    "3:4":  {"width": 1728, "height": 2304},
    "16:9": {"width": 2688, "height": 1512},
    "9:16": {"width": 1512, "height": 2688}
}

# 4K 超高清版 (约 8MP-12MP)
SIZE_MAP_4K = {
    "1:1":  {"width": 3072, "height": 3072},
    "4:3":  {"width": 3840, "height": 2880},
    "3:4":  {"width": 2880, "height": 3840},
    "16:9": {"width": 3840, "height": 2160},
    "9:16": {"width": 2160, "height": 3840}
}

OPENAI_SIZE_MAP = {
    "1:1": "1024x1024",
    "4:3": "1024x768",
    "3:4": "768x1024",
    "16:9": "1280x720",
    "9:16": "720x1280"
}

class BananaService:
    def _make_request(self, method, url, headers, json_data=None, files=None, data=None, timeout=120):
        import time
        max_retries = 3
        retry_count = 0
        last_error = None

        while retry_count <= max_retries:
            try:
                if method == "POST":
                    if files:
                        response = requests.post(url, headers=headers, files=files, data=data, timeout=timeout, proxies={"http": None, "https": None})
                    else:
                        response = requests.post(url, json=json_data, headers=headers, timeout=timeout, proxies={"http": None, "https": None})
                else:
                    response = requests.get(url, headers=headers, timeout=timeout, proxies={"http": None, "https": None})
                
                if response.status_code in [502, 503, 504]:
                    raise requests.exceptions.HTTPError(f"Server Error {response.status_code}", response=response)
                
                response.raise_for_status()
                return response
            except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError, 
                    requests.exceptions.ChunkedEncodingError, requests.exceptions.HTTPError,
                    requests.exceptions.Timeout) as e:
                last_error = e
                retry_count += 1
                print(f"DEBUG_LOG: Request failed (Attempt {retry_count}/{max_retries + 1}): {type(e).__name__}: {e}")
                if retry_count <= max_retries:
                    wait_time = 2 * retry_count
                    print(f"DEBUG_LOG: Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    break
            except Exception as e:
                raise e
        
        if last_error:
            error_detail = ""
            if hasattr(last_error, 'response') and last_error.response is not None:
                try:
                    error_detail = f" - Detail: {last_error.response.text}"
                except:
                    pass
            raise Exception(f"API请求失败(已重试{max_retries}次): {str(last_error)}{error_detail}")

    def generate_image(self, prompt: str, ratio: str, image: bytes = None, mask: bytes = None, model_id: str = "nano_banana_2", api_key: str = None, api_url: str = None):
        # Get model config
        model_config = MODEL_REGISTRY.get(model_id)
        if not model_config:
            print(f"DEBUG_LOG: Model {model_id} not found, falling back to nano_banana_2")
            model_config = MODEL_REGISTRY["nano_banana_2"]
        
        print(f"DEBUG_LOG: Using Model: {model_config['name']} ({model_id})")
            
        # 智能尺寸选择
        model_id_lower = model_id.lower()
        if "4k" in model_id_lower:
            size_config = SIZE_MAP_4K.get(ratio, SIZE_MAP_4K["1:1"])
            print(f"DEBUG_LOG: Resolution Tier: 4K")
        elif "2k" in model_id_lower or "doubao" in model_id_lower:
            size_config = SIZE_MAP_2K.get(ratio, SIZE_MAP_2K["1:1"])
            print(f"DEBUG_LOG: Resolution Tier: 2K")
        else:
            size_config = SIZE_MAP_1K.get(ratio, SIZE_MAP_1K["1:1"])
            print(f"DEBUG_LOG: Resolution Tier: 1K")
            
        width = size_config["width"]
        height = size_config["height"]
        
        base_url = api_url.rstrip('/') if api_url else model_config["url"].rstrip('/')
        real_model_id = model_config["model_key"]
        provider = model_config.get("provider", "default")

        # Determine API Key
        final_api_key = api_key if api_key else config.BANANA_API_KEY
        if final_api_key:
            final_api_key = final_api_key.strip()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {final_api_key}"
        }

        print(f"DEBUG_LOG: 用户选择={ratio}, 正在发送尺寸: {width} x {height}, 模型ID: {real_model_id}")

        if image and provider == "comfly":
            # --- Image-to-Image (Multipart) ---
            url = f"{base_url}/images/edits"
            files = {'image': ('image.png', image, 'image/png')}
            if mask:
                files['mask'] = ('mask.png', mask, 'image/png')
            
            data = {
                "prompt": prompt,
                "model": real_model_id,
                "n": 1,
                "aspect_ratio": ratio,
                "size": f"{width}x{height}",
                "strength": 0.7,
                "response_format": "url"
            }
            if real_model_id == "nano-banana-2-2k":
                data["image_size"] = "1K"
            
            if "Content-Type" in headers:
                del headers["Content-Type"]
                
            print(f"DEBUG_LOG: Sending Multipart Request (Img2Img). URL={url}")
            response = self._make_request("POST", url, headers=headers, files=files, data=data)
            
        elif provider == "openai":
            # --- OpenAI Format ---
            url = f"{base_url}/images/generations"
            openai_size = OPENAI_SIZE_MAP.get(ratio, "1024x1024")
            current_payload = {
                "model": real_model_id,
                "prompt": prompt,
                "size": openai_size,
                "n": 1,
                "response_format": "url"
            }
            print(f"DEBUG_LOG: Sending OpenAI Request. URL={url}")
            response = self._make_request("POST", url, headers=headers, json_data=current_payload)
            
        else:
            # --- Standard JSON Request ---
            url = f"{base_url}/images/generations"
            
            current_payload = {
                "prompt": prompt,
                "negative_prompt": "",
                "model": real_model_id,
            }
            
            if provider == "comfly_json":
                current_payload.update({
                    "size": f"{width}x{height}",
                    "n": 1,
                    "response_format": "url"
                })
                if real_model_id == "nano-banana-2-2k":
                    current_payload["image_size"] = "1K"
                if image:
                    base64_data = base64.b64encode(image).decode('utf-8')
                    current_payload["image"] = f"data:image/png;base64,{base64_data}"
                    current_payload["strength"] = 0.7
            else:
                # Use aspect_ratio for standard ratios, width/height for others
                standard_ratios = ["1:1", "4:3", "3:4", "16:9", "9:16"]
                if ratio in standard_ratios:
                    current_payload["aspect_ratio"] = ratio
                else:
                    current_payload["width"] = width
                    current_payload["height"] = height
                    
                if image:
                    current_payload["image"] = base64.b64encode(image).decode('utf-8')
                    current_payload["strength"] = 0.7

            print(f"DEBUG_LOG: Sending JSON Request. URL={url}")
            print(f"DEBUG_LOG: Payload: {json.dumps(current_payload, indent=2)}")
            response = self._make_request("POST", url, headers=headers, json_data=current_payload)

        try:
            response.raise_for_status()
            result = response.json()
            print(f"DEBUG_LOG: API Response Type: {type(result)}")
            
            if not isinstance(result, dict):
                print(f"DEBUG_LOG: API Response Content: {result}")
                if isinstance(result, list) and len(result) > 0:
                    # If it's a list, maybe the first item is what we want
                    item = result[0]
                    if isinstance(item, str): return item
                    if isinstance(item, dict): result = item
                else:
                    return str(result)

            print(f"DEBUG_LOG: API Response Keys: {list(result.keys())}")
            
            # Try to find image in various common locations
            if "output" in result and result["output"]:
                 if isinstance(result["output"], list) and len(result["output"]) > 0:
                     return result["output"][0]
                 return result["output"]
            
            if "data" in result and isinstance(result["data"], list) and len(result["data"]) > 0:
                item = result["data"][0]
                if isinstance(item, dict):
                    if "url" in item:
                        return item["url"]
                    if "b64_json" in item:
                        return item["b64_json"]
                elif isinstance(item, str):
                    return item
            
            # Doubao 4.5 specific response handling if needed
            if "image_url" in result:
                return result["image_url"]

            # Fallback to root url or other common fields
            for key in ["url", "image", "img_url"]:
                if key in result and result[key]:
                    return result[key]

            print(f"DEBUG_LOG: Could not find image in response: {result}")
            return ""
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.text # Use text to be safe
                    print(f"API Error Detail: {error_detail}")
                    error_msg = f"{str(e)} - Detail: {error_detail}"
                except:
                    error_msg = f"{str(e)} - Detail: (could not read response text)"
            else:
                print(f"Local Error: {str(e)}")
            
            # Log to file
            with open("backend_error.log", "a", encoding="utf-8") as f:
                import datetime
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{now}] Error: {error_msg}\n")
            
            print(f"Error generating image: {error_msg}")
            import traceback
            traceback.print_exc()
            raise Exception(error_msg)

banana_service = BananaService()
