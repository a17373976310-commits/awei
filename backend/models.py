# backend/models.py
from .config import config

# Model Registry
# Format:
# "model_id": {
#     "name": "Display Name",
#     "url": "API Endpoint URL",
#     "model_key": "Model Key (if needed by API)",
#     "description": "Short description"
# }

MODEL_REGISTRY = {
    "nano_banana_2": {
        "name": "Nano Banana 2 (基础版)",
        "url": config.BANANA_API_URL, # Default from config
        "model_key": config.BANANA_MODEL_KEY,
        "description": "速度快，通用性强",
        "provider": "default"
    },
    "comfly_nano_banana": {
        "name": "Comfly Nano Banana 2 (官方源)",
        "url": "https://ai.comfly.chat/v1",
        "model_key": "nano-banana-2",
        "description": "Comfly 官方渠道，支持文生图与图生图",
        "provider": "comfly"
    },

    "nano_banana_official": {
        "name": "Nano Banana (Google)",
        "url": "https://ai.comfly.chat/v1",
        "model_key": "nano-banana",
        "description": "Google 最先进的图像生成和编辑模型，支持文生图、图生图、多图生图",
        "provider": "comfly"
    },

    "doubao_seedream_4_0": {
        "name": "Doubao Seedream 4.0 (即梦4)",
        "url": "https://ai.comfly.chat/v1",
        "model_key": "doubao-seedream-4-0-250828",
        "description": "字节跳动最新即梦4.0模型，画质细腻",
        "provider": "comfly"
    },
    "doubao_seedream_4_5": {
        "name": "Doubao Seedream 4.5 (即梦4.5)",
        "url": "https://ai.comfly.chat/v1",
        "model_key": "doubao-seedream-4-5-251128",
        "description": "字节跳动最新即梦4.5模型，支持多模态生成",
        "provider": "comfly_json"
    }
}
