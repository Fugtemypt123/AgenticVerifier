 #!/usr/bin/env python3
"""
Standalone test script for the Verifier Agent.
This script connects to the verifier MCP server and demonstrates its functionality.
"""
import asyncio
import argparse
import os
import sys
import tempfile
from pathlib import Path
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image, ImageDraw
from prompts.blender import blender_verifier_hints

api_key = os.getenv("OPENAI_API_KEY")

class VerifierTester:
    def __init__(self):
        self.session = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_verifier(self, verifier_script_path: str):
        """Connect to the Verifier MCP server."""
        server_params = StdioServerParameters(
            command="python",
            args=[verifier_script_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print(f"Connected to Verifier with tools: {[tool.name for tool in tools]}")

    def create_test_images(self, target_dir: str, render_dir: str):
        """Create test images for verification."""
        os.makedirs(target_dir, exist_ok=True)
        os.makedirs(render_dir, exist_ok=True)
        
        # Create target images
        target1 = Image.new('RGB', (400, 300), 'lightblue')
        draw1 = ImageDraw.Draw(target1)
        draw1.rectangle([100, 100, 300, 200], fill='red')
        draw1.text((150, 250), "Target Scene", fill='black')
        target1.save(os.path.join(target_dir, 'render1.png'))
        
        target2 = Image.new('RGB', (400, 300), 'lightgreen')
        draw2 = ImageDraw.Draw(target2)
        draw2.circle([200, 150], 50, fill='blue')
        draw2.text((150, 250), "Target View 2", fill='black')
        target2.save(os.path.join(target_dir, 'render2.png'))
        
        # Create current render images (slightly different)
        render1 = Image.new('RGB', (400, 300), 'lightblue')
        draw_r1 = ImageDraw.Draw(render1)
        draw_r1.rectangle([110, 110, 290, 190], fill='darkred')  # Slightly different
        draw_r1.text((150, 250), "Current Scene", fill='black')
        render1.save(os.path.join(render_dir, 'render1.png'))
        
        render2 = Image.new('RGB', (400, 300), 'lightgreen')
        draw_r2 = ImageDraw.Draw(render2)
        draw_r2.circle([210, 160], 45, fill='darkblue')  # Slightly different
        draw_r2.text((150, 250), "Current View 2", fill='black')
        render2.save(os.path.join(render_dir, 'render2.png'))
        
        print(f"Created test images in {target_dir} and {render_dir}")

    async def test_verifier_workflow(self, args):
        """Test the complete verifier workflow."""
        print("\n=== Testing Verifier Agent ===")
        
        # Create test images
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = os.path.join(temp_dir, "target")
            render_dir = os.path.join(temp_dir, "renders")
            self.create_test_images(target_dir, render_dir)
            
            # 1. Create verification session
            print("Step 1: Creating verification session...")
            session_result = await self.session.call_tool("create_verification_session", {
                "vision_model": args.vision_model,
                "api_key": api_key,
                "thoughtprocess_save": args.thoughtprocess_save,
                "max_rounds": args.max_rounds,
                "verifier_hints": args.verifier_hints,
                "target_image_path": target_dir,
                "blender_save": args.blender_save
            })
            print(f"Session result: {session_result.content}")
            
            if not self._is_success(session_result):
                print("Failed to create verification session")
                return
            
            # Extract session ID
            session_id = self._extract_session_id(session_result)
            if not session_id:
                print("Failed to extract session ID")
                return
            
            print(f"Created session: {session_id}")
            
            # 2. Test PIL code execution
            print("\nStep 2: Testing PIL code execution...")
            pil_code = """
from PIL import Image, ImageDraw
import io
import base64

# Create a test image
img = Image.new('RGB', (200, 200), 'white')
draw = ImageDraw.Draw(img)
draw.rectangle([50, 50, 150, 150], fill='green')
draw.text((75, 175), "Test PIL", fill='black')
result = img
"""
            pil_result = await self.session.call_tool("exec_pil_code", {
                "code": pil_code
            })
            print(f"PIL execution result: Success={self._check_pil_success(pil_result)}")
            
            # 3. Test image comparison
            print("\nStep 3: Testing image comparison...")
            compare_result = await self.session.call_tool("compare_images", {
                "path1": os.path.join(target_dir, 'render1.png'),
                "path2": os.path.join(render_dir, 'render1.png'),
                "api_key": args.api_key
            })
            print(f"Image comparison completed: {len(str(compare_result.content)) > 50}")
            
            # 4. Verify scene
            print("\nStep 4: Verifying scene...")
            test_code = """
import bpy
# Test scene code
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
cube = bpy.context.active_object
cube.name = "TestCube"
"""
            verify_result = await self.session.call_tool("verify_scene", {
                "session_id": session_id,
                "code": test_code,
                "render_path": render_dir,
                "round_num": 0
            })
            print(f"Scene verification result: {verify_result.content}")
            
            # 5. Save thought process
            print("\nStep 5: Saving thought process...")
            save_result = await self.session.call_tool("save_thought_process", {
                "session_id": session_id
            })
            print(f"Save result: {save_result.content}")
            
            # 6. Get session info
            print("\nStep 6: Getting session info...")
            info_result = await self.session.call_tool("get_session_info", {
                "session_id": session_id
            })
            print(f"Session info: {info_result.content}")
            
            print("\n=== Verifier Test Complete ===")

    def _is_success(self, result):
        """Check if the result indicates success."""
        if result.content and len(result.content) > 0:
            content = result.content[0].text
            return '"status": "success"' in content or '"status":"success"' in content
        return False

    def _check_pil_success(self, result):
        """Check if PIL execution was successful."""
        if result.content and len(result.content) > 0:
            content = result.content[0].text
            return '"success": true' in content or '"success":true' in content
        return False

    def _extract_session_id(self, result):
        """Extract session ID from result."""
        if result.content and len(result.content) > 0:
            content = result.content[0].text
            try:
                # Simple extraction - in real implementation you'd parse JSON properly
                start = content.find('"session_id": "') + len('"session_id": "')
                end = content.find('"', start)
                if start > len('"session_id": "') - 1 and end > start:
                    return content[start:end]
            except:
                pass
        return None

    async def cleanup(self):
        """Clean up resources."""
        await self.exit_stack.aclose()

async def main():
    parser = argparse.ArgumentParser(description="Test Verifier Agent")
    parser.add_argument("--verifier-script", default="agents/verifier_mcp.py",
                       help="Path to verifier MCP script")
    parser.add_argument("--vision-model", default="gpt-4o",
                       help="OpenAI vision model to use")
    parser.add_argument("--thoughtprocess-save", default="test_verifier_thought.json",
                       help="Path to save thought process")
    parser.add_argument("--max-rounds", type=int, default=3,
                       help="Maximum number of rounds")
    parser.add_argument("--verifier-hints", default=blender_verifier_hints["shape"],
                       help="Hints for verifier")
    parser.add_argument("--blender-save", default=None,
                       help="Blender save path")
    
    args = parser.parse_args()
    
    # Validate required files
    if not os.path.exists(args.verifier_script):
        print(f"Error: Verifier script not found: {args.verifier_script}")
        sys.exit(1)
    
    tester = VerifierTester()
    try:
        await tester.connect_to_verifier(args.verifier_script)
        await tester.test_verifier_workflow(args)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())