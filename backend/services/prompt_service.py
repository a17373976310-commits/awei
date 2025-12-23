import requests
import base64
import json
from typing import List
from ..config import config
from ..prompts import PRODUCT_LOCK_PROMPT, MAIN_ENGINE_INSTRUCTION, PROMPT_REGISTRY, PROMPT_TEMPLATES

class PromptService:
    def optimize_prompt(self, prompt: str, scenario: str, image_bytes_list: List[bytes] = None, api_key: str = None) -> str:
        print(f"DEBUG_LOG: optimize_prompt called. Scenario: {scenario}, Image Count: {len(image_bytes_list) if image_bytes_list else 0}")
        
        final_api_key = api_key if api_key else config.BANANA_API_KEY
        if not final_api_key:
            print("ERROR: No API Key provided for optimization.")
            return prompt

        # 1. Stage 1: Multi-view Visual Fingerprint Extraction
        fingerprint = {}
        if image_bytes_list:
            print(f"DEBUG_LOG: Stage 1 - Extracting Fingerprint from {len(image_bytes_list)} images...")
            fingerprint = self._extract_fingerprint(image_bytes_list, final_api_key)
            print(f"DEBUG_LOG: Fingerprint: {fingerprint}")

        # 2. Stage 2: Dual-Core Prompt Engine
        print(f"DEBUG_LOG: Stage 2 - Generating Dual-Core Prompts for scenario: {scenario}")
        optimized_json = self._generate_dual_core_prompts(prompt, scenario, fingerprint, image_bytes_list, final_api_key)
        
        return optimized_json

    def _extract_fingerprint(self, image_bytes_list: List[bytes], api_key: str) -> dict:
        url = "https://ai.comfly.chat/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # Prepare content with multiple images
        content_list = [
            {"type": "text", "text": "Analyze these product images and extract the visual fingerprint."}
        ]
        
        for img_bytes in image_bytes_list:
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            content_list.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })
        
        # Format the system prompt with image count
        system_prompt = PRODUCT_LOCK_PROMPT.format(img_count=len(image_bytes_list))
        
        payload = {
            "model": "gemini-3-pro-preview",
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": content_list
                }
            ],
            "response_format": {"type": "json_object"}
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45, proxies={"http": None, "https": None})
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            print(f"ERROR: Fingerprint extraction failed: {e}")
            return {}

    def _generate_dual_core_prompts(self, user_prompt: str, scenario: str, fingerprint: dict, image_bytes_list: List[bytes], api_key: str) -> str:
        url = "https://ai.comfly.chat/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        # Get mode template
        mode_template = PROMPT_REGISTRY.get(scenario, PROMPT_TEMPLATES.get(scenario, "General Mode"))
        
        system_content = f"{MAIN_ENGINE_INSTRUCTION}\n\n# Current Mode Template\n{mode_template}"
        
        user_text = f"User Request: {user_prompt}"
        if fingerprint:
            user_text += f"\n\n[Subject Lock - Visual Fingerprint]:\n{json.dumps(fingerprint, indent=2, ensure_ascii=False)}"

        user_content = [{"type": "text", "text": user_text}]
        
        # Include all images in stage 2 as well for full context
        if image_bytes_list:
            for img_bytes in image_bytes_list:
                base64_image = base64.b64encode(img_bytes).decode('utf-8')
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                })

        payload = {
            "model": "gemini-3-pro-preview",
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"}
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45, proxies={"http": None, "https": None})
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            # Validate it's proper JSON
            json.loads(content) 
            return content
        except Exception as e:
            print(f"ERROR: Dual-core prompt generation failed: {e}")
            import traceback
            traceback.print_exc()
            # Fallback
            fallback = {
                "nano_banana_en": f"{user_prompt}, high quality, 4k",
                "seadream_cn": f"{user_prompt}, 高质量, 4k",
                "layout_logic": "Default layout."
            }
            return json.dumps(fallback, ensure_ascii=False)

prompt_service = PromptService()
