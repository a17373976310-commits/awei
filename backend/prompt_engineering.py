# backend/prompt_engineering.py

"""
Prompt Engineering Module
This file contains advanced prompt templates and logic for the E-commerce AI system.
"""

# ==============================================================================
# 核心辅助模式: 产品锁定 (Product DNA Lock)
# ==============================================================================
PRODUCT_LOCK_TEMPLATE = """
# Role: Industrial Design & Visual Analyst
# Task: 分析用户上传的多视角图（共 {{img_count}} 张）。提取产品的"像素指纹"以锁定 3D DNA。

# 🧠 Analysis Logic:
1. [Geometry]: 提取产品的 3D 轮廓、线条比例及特有曲线。
2. [Branding]: 识别 Logo 字体、颜色及在产品上的精确坐标。
3. [Material]: 识别核心材质（如：哑光涂层、拉丝金属、透明玻璃、磨砂塑料）。

# Output Format (Strict JSON):
{{
  "unified_desc": "针对AI渲染的详细物理描述",
  "materials": "材质关键词组合",
  "branding": "Logo特征与位置说明",
  "dna_summary": "一句话核心视觉特征"
}}
"""

# ==============================================================================
# 模式: 淘宝详情页 - 场景氛围融合版 (Taobao Detail Visual)
# ==============================================================================
TAOBAO_DETAIL_TEMPLATE = """
# Role
You are a Lifestyle Photographer for E-commerce Detail Pages.

# Task
Create an immersive, mood-setting "Key Visual" for the product detail page.

# 🧠 Logic
1. **Context**: Where is this product used? (e.g. Sofa -> Cozy Living Room).
2. **Emotion**: How should the user feel? (Relaxed, Energized, Safe).
3. **Copywriting**: 如果用户未提供文案，请**自动脑补** 1-2 条具有情绪感染力的短句。

# 🎨 The "Detail Template" (STRICT OUTPUT FORMAT)
Output structure (Use Simplified Chinese for Text Content):
---
[Visual Description]
"一张极具生活气息的场景摄影。主体[Product]自然地融入在[Scenario]中。
光线是[Time of Day, e.g. Morning Sun], 营造出[Mood]的氛围。
画面中包含[Lifestyle Props, e.g. a book, a cup of coffee]来暗示使用场景。"

[Text & UI Layout]
"***Layout Style**: Natural Integration (场景融合排版).
Text Rendering Instructions:
1. **Mood Title**: 内容: "[User Main Title or Brainstormed]". Style: [Elegant Serif or Handwritten]. Position: [Floating in negative space].
2. **Description**: 内容: "[User Sub Title or Brainstormed]". Style: [Clean Sans-serif, smaller].
"
---
# Output
Output ONLY the final structured prompt.
"""

# ==============================================================================
# 提示词工程注册表 (Prompt Engineering Registry)
# ==============================================================================
PROMPT_TEMPLATES = {
    "product_lock": PRODUCT_LOCK_TEMPLATE,
    "taobao_detail": TAOBAO_DETAIL_TEMPLATE,
}

def get_template(scenario):
    return PROMPT_TEMPLATES.get(scenario, "General Mode")
