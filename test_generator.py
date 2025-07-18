#!/usr/bin/env python3
"""
Standalone test script for the Generator Agent.
This script connects to the generator MCP server and demonstrates its functionality.
"""
import asyncio
import argparse
import os
import sys
import json
from pathlib import Path
from contextlib import AsyncExitStack
from typing import Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent
from prompts.blender import blender_generator_hints

api_key = os.getenv("OPENAI_API_KEY")

class GeneratorTester:
    def __init__(self):
        self.generator_session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_generator(self, generator_script_path: str):
        """Connect to the Generator MCP server."""
        server_params = StdioServerParameters(
            command="python",
            args=[generator_script_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.generator_session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.generator_session.initialize()
        
        # List available tools
        response = await self.generator_session.list_tools()
        tools = response.tools
        print(f"Connected to Generator with tools: {[tool.name for tool in tools]}")

    def _extract_code_from_result(self, result):
        """Extract generated code from the result."""
        if result.content and len(result.content) > 0:
            content_item = result.content[0]
            if isinstance(content_item, TextContent):
                content = content_item.text
                try:
                    # Parse JSON response to extract code
                    json_data = json.loads(content)
                    if 'code' in json_data:
                        return json_data['code']
                    elif 'current_code' in json_data:
                        return json_data['current_code']
                    elif 'generated_code' in json_data:
                        return json_data['generated_code']
                except json.JSONDecodeError:
                    pass
        return None

    def _extract_execution_result(self, result):
        """Extract execution result from the result."""
        if result.content and len(result.content) > 0:
            content_item = result.content[0]
            if isinstance(content_item, TextContent):
                content = content_item.text
                try:
                    json_data = json.loads(content)
                    return json_data.get('execution_result')
                except json.JSONDecodeError:
                    pass
        return None

    async def test_generator_workflow(self, args):
        """Test the complete generator workflow."""
        print("\n=== Testing Generator Agent ===")
        
        # Ensure generator session is initialized
        if self.generator_session is None:
            print("Error: Generator session not initialized")
            return
        
        # 1. Initialize generator
        print("Step 1: Initializing generator...")
        init_result = await self.generator_session.call_tool("initialize_generator", {
            "vision_model": args.vision_model,
            "api_key": api_key,
            "thoughtprocess_save": args.thoughtprocess_save,
            "max_rounds": args.max_rounds,
            "generator_hints": args.generator_hints,
            "init_code": args.init_code,
            "init_image_path": args.init_image_path,
            "target_image_path": args.target_image_path,
            "target_description": args.target_description,
            "blender_server_path": args.blender_server_path
        })
        print(f"Initialization result: {init_result.content}")
        
        if not self._is_success(init_result):
            print("Failed to initialize generator")
            return
        
        # 2. Setup Blender executor
        print("Step 2: Setting up Blender executor...")
        blender_setup_result = await self.generator_session.call_tool("setup_blender_executor", {
            "blender_command": args.blender_command,
            "blender_file": args.blender_file,
            "blender_script": args.blender_script,
            "script_save": args.script_save,
            "render_save": args.render_save,
            "blender_save": args.blender_save
        })
        print(f"Blender setup result: {blender_setup_result.content}")
        
        if not self._is_success(blender_setup_result):
            print("Failed to setup Blender executor")
            return
        
        # 3. Generate initial code (with automatic Blender execution)
        print("\nStep 3: Generating initial code (with automatic execution)...")
        gen_result = await self.generator_session.call_tool("generate_code", {})
        print(f"Generation result: {gen_result.content}")
        
        if not self._is_success(gen_result):
            print("Failed to generate initial code")
            return
        
        # Check if Blender execution happened automatically
        execution_result = self._extract_execution_result(gen_result)
        if execution_result:
            print("✅ Automatic Blender execution completed!")
            if execution_result.get('status') == 'success':
                print("   - Blender execution was successful")
                blender_result = execution_result.get('result', {})
                if blender_result.get('status') == 'success':
                    print("   - Image rendering successful")
                else:
                    print(f"   - Image rendering failed: {blender_result.get('output', 'Unknown error')}")
            else:
                print(f"   - Blender execution failed: {execution_result.get('error', 'Unknown error')}")
        else:
            print("⚠️  No automatic Blender execution detected")
        
        # 4. Add feedback and generate again
        print("\nStep 4: Adding feedback and generating again...")
        feedback_text = "The code looks good, but please add more detailed comments to explain each step."
        feedback_result = await self.generator_session.call_tool("add_feedback", {
            "feedback": feedback_text
        })
        print(f"Feedback result: {feedback_result.content}")
        
        gen_result2 = await self.generator_session.call_tool("generate_code", {})
        print(f"Second generation result: {gen_result2.content}")
        
        # Check second execution
        execution_result2 = self._extract_execution_result(gen_result2)
        if execution_result2:
            print("✅ Second automatic Blender execution completed!")
        
        # 5. Save thought process
        print("\nStep 5: Saving thought process...")
        save_result = await self.generator_session.call_tool("save_thought_process", {})
        print(f"Save result: {save_result.content}")
        
        # 6. Get memory
        print("\nStep 6: Getting memory...")
        memory_result = await self.generator_session.call_tool("get_memory", {})
        memory_length = 0
        if memory_result.content and len(memory_result.content) > 0:
            content_item = memory_result.content[0]
            if isinstance(content_item, TextContent):
                memory_length = len(content_item.text)
        print(f"Memory length: {memory_length}")
        
        # 7. Test cleanup
        print("\nStep 7: Testing cleanup...")
        cleanup_result = await self.generator_session.call_tool("cleanup_generator", {})
        print(f"Cleanup result: {cleanup_result.content}")
        
        print("\n=== Generator Test Complete ===")

    def _is_success(self, result):
        """Check if the result indicates success."""
        if result.content and len(result.content) > 0:
            content_item = result.content[0]
            if isinstance(content_item, TextContent):
                content = content_item.text
                return '"status": "success"' in content or '"status":"success"' in content
        return False

    async def cleanup(self):
        """Clean up resources."""
        await self.exit_stack.aclose()

async def main():
    parser = argparse.ArgumentParser(description="Test Generator Agent")
    parser.add_argument("--generator-script", default="agents/generator_mcp.py",
                       help="Path to generator MCP script")
    parser.add_argument("--vision-model", default="gpt-4o",
                       help="OpenAI vision model to use")
    parser.add_argument("--thoughtprocess-save", default="_test/test_generator_thought.json",
                       help="Path to save thought process")
    parser.add_argument("--max-rounds", type=int, default=5,
                       help="Maximum number of rounds")
    parser.add_argument("--generator-hints", default=blender_generator_hints["shape"],
                       help="Hints for generator")
    initial_code = Path("data/blendergym/blendshape1/start.py").read_text()
    parser.add_argument("--init-code", default=initial_code,
                       help="Initial code")
    parser.add_argument("--init-image-path", default="data/blendergym/blendshape1/renders/start",
                       help="Path to initial images")
    parser.add_argument("--target-image-path", default="data/blendergym/blendshape1/renders/goal",
                       help="Path to target images")
    parser.add_argument("--target-description", default="A simple test scene",
                       help="Target description")
    
    # Blender execution parameters
    parser.add_argument("--blender-command", default="utils/blender/infinigen/blender/blender",
                       help="Blender command path")
    parser.add_argument("--blender-file", default="data/blendergym/blendshape1/blender_file.blend",
                       help="Blender template file")
    parser.add_argument("--blender-script", default="data/blendergym/pipeline_render_script.py",
                       help="Blender execution script")
    parser.add_argument("--script-save", default="_test",
                       help="Directory to save generated scripts")
    parser.add_argument("--render-save", default="_test",
                       help="Directory to save rendered images")
    parser.add_argument("--blender-save", default=None,
                       help="Optional Blender save file")
    
    # Tool server paths
    parser.add_argument("--blender-server-path", default="servers/generator/blender.py",
                       help="Path to Blender MCP server script")
    
    args = parser.parse_args()
    
    # Validate required files
    if not os.path.exists(args.generator_script):
        print(f"Error: Generator script not found: {args.generator_script}")
        sys.exit(1)
    
    # Create output directory
    os.makedirs("_test", exist_ok=True)
    
    tester = GeneratorTester()
    try:
        await tester.connect_to_generator(args.generator_script)
        await tester.test_generator_workflow(args)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())