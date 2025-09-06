#!/usr/bin/env python3
"""
Web comparison server for Design2Code mode.
Handles comparison between generated HTML screenshots and target designs.
"""
import os
import base64
import io
import logging
from typing import Dict, List, Optional
from PIL import Image, ImageChops, ImageEnhance
import numpy as np
from mcp.server.fastmcp import FastMCP
from openai import OpenAI

# Create MCP instance
mcp = FastMCP("web-comparison")

# Global tool instance
_web_tool = None

class WebComparisonTool:
    """Tool for comparing generated web pages with target designs."""
    
    def __init__(self, vision_model: str = "gpt-4o", api_key: str = None, api_base_url: str = None):
        self.model = vision_model
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("OpenAI API key must be provided.")
        self.api_base_url = api_base_url or "https://api.openai.com/v1"
        self.client = OpenAI(api_key=self.api_key, base_url=self.api_base_url)

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def _highlight_differences(self, img1: Image.Image, img2: Image.Image, 
                             threshold: int = 50) -> tuple:
        """Highlight differences between two images."""
        # Ensure both images are the same size
        if img1.size != img2.size:
            img2 = img2.resize(img1.size, Image.Resampling.LANCZOS)
        
        # Convert to numpy arrays
        img1_array = np.array(img1.convert('RGB'))
        img2_array = np.array(img2.convert('RGB'))
        
        # Calculate difference
        diff_array = np.abs(img1_array.astype(np.int16) - img2_array.astype(np.int16))
        diff_array = np.clip(diff_array, 0, 255).astype(np.uint8)
        
        # Create mask for significant differences
        mask = np.any(diff_array > threshold, axis=2)
        
        # Highlight differences in red
        highlight_color = np.array([255, 0, 0])
        img1_highlighted = img1_array.copy()
        img2_highlighted = img2_array.copy()
        
        img1_highlighted[mask] = ((img1_highlighted[mask] * 0.5 + highlight_color * 0.5)).astype(np.uint8)
        img2_highlighted[mask] = ((img2_highlighted[mask] * 0.5 + highlight_color * 0.5)).astype(np.uint8)
        
        return Image.fromarray(img1_highlighted), Image.fromarray(img2_highlighted), Image.fromarray(diff_array)

    def compare_designs(self, generated_path: str, target_path: str) -> Dict:
        """
        Compare generated HTML screenshot with target design.
        
        Args:
            generated_path: Path to generated HTML screenshot
            target_path: Path to target design image
            
        Returns:
            Dict with comparison results
        """
        try:
            # Load images
            generated_img = Image.open(generated_path).convert('RGB')
            target_img = Image.open(target_path).convert('RGB')
            
            # Highlight differences
            img1_highlighted, img2_highlighted, diff_img = self._highlight_differences(
                generated_img, target_img
            )
            
            # Convert to base64 for API
            images_b64 = [
                self._image_to_base64(generated_img),
                self._image_to_base64(target_img),
                self._image_to_base64(img1_highlighted),
                self._image_to_base64(img2_highlighted),
                self._image_to_base64(diff_img)
            ]
            
            # Create comparison prompt
            messages = [
                {
                    "role": "system", 
                    "content": """You are an expert web developer and UI/UX designer. Your task is to compare a generated HTML webpage screenshot with the original design target and provide detailed feedback.

Focus on:
1. **Layout Structure**: Overall page structure, positioning, spacing
2. **Visual Design**: Colors, typography, styling, visual hierarchy
3. **Content Accuracy**: Text content, images, interactive elements
4. **Responsive Design**: How the layout adapts to different screen sizes
5. **Accessibility**: Semantic structure, contrast, usability
6. **Code Quality**: Whether the implementation follows best practices

Provide specific, actionable feedback. If the implementation is very close to the design, say "OK! The generated code successfully matches the design and is ready for production." Otherwise, list the main issues that need to be addressed."""
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please compare the generated HTML webpage (first image) with the target design (second image). The third and fourth images show highlighted differences, and the fifth image shows the raw difference map. Focus on the highlighted areas and provide detailed feedback on what needs to be improved."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{images_b64[0]}"}},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{images_b64[1]}"}},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{images_b64[2]}"}},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{images_b64[3]}"}},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{images_b64[4]}"}}
                    ]
                }
            ]
            
            # Get AI comparison
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1000
            )
            
            comparison_text = response.choices[0].message.content
            
            # Calculate similarity score (simple pixel difference)
            diff_array = np.array(diff_img)
            total_pixels = diff_array.size
            different_pixels = np.sum(diff_array > 50)  # threshold for "different"
            similarity_score = 1.0 - (different_pixels / total_pixels)
            
            return {
                "status": "success",
                "comparison": comparison_text,
                "similarity_score": float(similarity_score),
                "different_pixels": int(different_pixels),
                "total_pixels": int(total_pixels)
            }
            
        except Exception as e:
            logging.error(f"Design comparison failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def analyze_html_structure(self, html_code: str) -> Dict:
        """
        Analyze HTML code structure and provide feedback.
        
        Args:
            html_code: The HTML code to analyze
            
        Returns:
            Dict with analysis results
        """
        try:
            messages = [
                {
                    "role": "system",
                    "content": """You are an expert web developer. Analyze the provided HTML/CSS code and provide feedback on:

1. **HTML Structure**: Semantic elements, proper nesting, accessibility
2. **CSS Quality**: Organization, modern features, responsive design
3. **Best Practices**: Code standards, performance, maintainability
4. **Potential Issues**: Common problems, browser compatibility, accessibility

Provide specific, actionable feedback."""
                },
                {
                    "role": "user",
                    "content": f"Please analyze this HTML/CSS code:\n\n```html\n{html_code}\n```"
                }
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=800
            )
            
            analysis = response.choices[0].message.content
            
            return {
                "status": "success",
                "analysis": analysis
            }
            
        except Exception as e:
            logging.error(f"HTML analysis failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

@mcp.tool()
def initialize_executor(vision_model: str, api_key: str, api_base_url: str = None) -> dict:
    """
    Initialize the web comparison tool.
    
    Args:
        vision_model: Vision model to use for comparison
        api_key: OpenAI API key
        api_base_url: Optional custom API base URL
    """
    global _web_tool
    try:
        _web_tool = WebComparisonTool(
            vision_model=vision_model,
            api_key=api_key,
            api_base_url=api_base_url
        )
        return {
            "status": "success",
            "message": "Web comparison tool initialized successfully"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool()
def compare_designs(generated_path: str, target_path: str) -> dict:
    """
    Compare generated HTML screenshot with target design.
    
    Args:
        generated_path: Path to generated HTML screenshot
        target_path: Path to target design image
    """
    global _web_tool
    if _web_tool is None:
        return {
            "status": "error",
            "error": "Web comparison tool not initialized. Call initialize_executor first."
        }
    
    try:
        result = _web_tool.compare_designs(generated_path, target_path)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool()
def analyze_html_structure(html_code: str) -> dict:
    """
    Analyze HTML code structure and provide feedback.
    
    Args:
        html_code: The HTML code to analyze
    """
    global _web_tool
    if _web_tool is None:
        return {
            "status": "error",
            "error": "Web comparison tool not initialized. Call initialize_executor first."
        }
    
    try:
        result = _web_tool.analyze_html_structure(html_code)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def main():
    """Main function to run the web comparison server."""
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
