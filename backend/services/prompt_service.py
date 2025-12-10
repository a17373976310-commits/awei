import requests
import base64
import json
from ..config import config
from ..prompts import PROMPT_TEMPLATES

class PromptService:
    def optimize_prompt(self, prompt: str, scenario: str, image_bytes: bytes = None, api_key: str = None) -> str:
        print(f"DEBUG_LOG: optimize_prompt called. Scenario: {scenario}, Has Image: {bool(image_bytes)}, Has Key: {bool(api_key)}")
        
        # Debug Log to file (Absolute Path)
        log_path = r"f:\网站1\prompt_debug.log"
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n--- New Request ---\nScenario: {scenario}\nPrompt: {prompt}\nHas API Key: {bool(api_key)}\n")
        except Exception as e:
            print(f"ERROR: Failed to write to log file: {e}")

        # 1. Check if scenario needs optimization
        if scenario in ["free_mode", "general"] or scenario not in PROMPT_TEMPLATES:
            print(f"DEBUG_LOG: Skipping optimization for scenario: {scenario}")
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"Skipping optimization. Reason: Scenario '{scenario}' is free/general or not in templates.\n")
            except: pass
            return prompt

        # 2. Get Template
        template = PROMPT_TEMPLATES[scenario]
        
        # 3. Prepare LLM Request
        # Use the Comfly Chat API (compatible with OpenAI format)
        url = "https://ai.comfly.chat/v1/chat/completions"
        final_api_key = api_key if api_key else config.BANANA_API_KEY
        
        if not final_api_key:
             with open("prompt_debug.log", "a", encoding="utf-8") as f:
                f.write("Optimization FAILED: No API Key provided.\n")
             return prompt
        
        # Model ID: User confirmed "gemini-3-pro-preview" via screenshot.
        model_id = "gemini-3-pro-preview" 

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {final_api_key}"
        }

        # Construct Messages
        messages = [
            {
                "role": "system",
                "content": template
            }
        ]

        user_content = [{"type": "text", "text": f"User Request: {prompt}"}]

        if image_bytes:
            # Add image for multimodal understanding
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })

        messages.append({
            "role": "user",
            "content": user_content
        })

        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000
        }

        try:
            print(f"DEBUG_LOG: Optimizing prompt with LLM ({model_id})...")
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"Sending request to LLM ({model_id})...\n")
            except: pass
                
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                optimized_content = result["choices"][0]["message"]["content"]
                print(f"DEBUG_LOG: Optimization successful. Length: {len(optimized_content)}")
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"Optimization SUCCESS. Content: {optimized_content[:100]}...\n")
                except: pass
                return optimized_content.strip()
            else:
                print("DEBUG_LOG: LLM returned no choices. Using original prompt.")
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write("Optimization FAILED: No choices returned.\n")
                except: pass
                return prompt
                
        except Exception as e:
            print(f"ERROR: Prompt optimization failed: {str(e)}")
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"Optimization ERROR: {str(e)}\n")
            except: pass
            # Fallback to original prompt + simple suffix if LLM fails
            return f"{prompt}, professional quality, 4k"

prompt_service = PromptService()
