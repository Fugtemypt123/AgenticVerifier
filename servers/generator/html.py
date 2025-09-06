#!/usr/bin/env python3
"""
HTML execution server for Design2Code mode.
Handles HTML/CSS code execution and screenshot generation.
"""
import os
import tempfile
import subprocess
import base64
import io
from pathlib import Path
from typing import Dict, Tuple, Optional
from PIL import Image
import logging
from mcp.server.fastmcp import FastMCP

# Create MCP instance
mcp = FastMCP("html-executor")

# Global executor instance
_executor = None

class HTMLExecutor:
    """Executes HTML/CSS code and generates screenshots."""
    
    def __init__(self, output_dir: str, browser_command: str = "google-chrome"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.browser_command = browser_command
        self.temp_dir = None
        
    def _setup_temp_dir(self):
        """Setup temporary directory for HTML files."""
        if self.temp_dir is None:
            self.temp_dir = tempfile.mkdtemp(prefix="design2code_")
        return self.temp_dir
    
    def _save_html_file(self, html_code: str, filename: str = "index.html") -> str:
        """Save HTML code to a temporary file."""
        temp_dir = self._setup_temp_dir()
        html_path = os.path.join(temp_dir, filename)
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_code)
        
        return html_path
    
    def _take_screenshot(self, html_path: str, output_path: str, 
                        width: int = 1920, height: int = 1080) -> Tuple[bool, str]:
        """Take a screenshot of the HTML page using headless browser."""
        try:
            # Use Chrome/Chromium in headless mode to take screenshot
            cmd = [
                self.browser_command,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size={},{}".format(width, height),
                "--screenshot={}".format(output_path),
                "file://{}".format(os.path.abspath(html_path))
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists(output_path):
                return True, "Screenshot taken successfully"
            else:
                return False, f"Browser error: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "Screenshot timeout"
        except FileNotFoundError:
            # Try alternative browser commands
            alternatives = ["chromium-browser", "chromium", "firefox"]
            for alt_browser in alternatives:
                try:
                    cmd[0] = alt_browser
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0 and os.path.exists(output_path):
                        return True, f"Screenshot taken with {alt_browser}"
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue
            return False, f"Browser not found. Tried: {self.browser_command}, {', '.join(alternatives)}"
        except Exception as e:
            return False, f"Screenshot error: {str(e)}"
    
    def _optimize_image(self, image_path: str) -> str:
        """Optimize the screenshot image."""
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize if too large (max 1920x1080)
                max_width, max_height = 1920, 1080
                if img.width > max_width or img.height > max_height:
                    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                
                # Save optimized version
                optimized_path = image_path.replace('.png', '_optimized.png')
                img.save(optimized_path, 'PNG', optimize=True, quality=85)
                
                return optimized_path
        except Exception as e:
            logging.warning(f"Image optimization failed: {e}")
            return image_path
    
    def execute(self, html_code: str, round_num: int) -> Dict:
        """Execute HTML code and generate screenshot."""
        try:
            # Save HTML file
            html_path = self._save_html_file(html_code, f"round_{round_num}.html")
            
            # Generate output path
            output_path = self.output_dir / f"round_{round_num}.png"
            
            # Take screenshot
            success, message = self._take_screenshot(html_path, str(output_path))
            
            if not success:
                return {
                    "status": "error",
                    "error": message,
                    "html_path": html_path
                }
            
            # Optimize image
            optimized_path = self._optimize_image(str(output_path))
            
            return {
                "status": "success",
                "output": optimized_path,
                "html_path": html_path,
                "message": message
            }
            
        except Exception as e:
            logging.error(f"HTML execution failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
                logging.info(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logging.warning(f"Failed to cleanup temp directory: {e}")

@mcp.tool()
def initialize_executor(output_dir: str, browser_command: str = "google-chrome") -> dict:
    """
    Initialize the HTML executor.
    
    Args:
        output_dir: Directory to save screenshots
        browser_command: Browser command to use for screenshots (default: google-chrome)
    """
    global _executor
    try:
        _executor = HTMLExecutor(output_dir, browser_command)
        return {
            "status": "success", 
            "message": f"HTML executor initialized with output directory: {output_dir}"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool()
def execute_html(html_code: str, round_num: int) -> dict:
    """
    Execute HTML code and generate screenshot.
    
    Args:
        html_code: The HTML/CSS code to execute
        round_num: Round number for file naming
    """
    global _executor
    if _executor is None:
        return {
            "status": "error", 
            "error": "HTML executor not initialized. Call initialize_executor first."
        }
    
    try:
        result = _executor.execute(html_code, round_num)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool()
def cleanup_executor() -> dict:
    """Clean up the HTML executor and temporary files."""
    global _executor
    try:
        if _executor:
            _executor.cleanup()
            _executor = None
        return {"status": "success", "message": "HTML executor cleaned up"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def main():
    """Main function to run the HTML executor as an MCP server."""
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
