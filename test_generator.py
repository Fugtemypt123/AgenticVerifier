 #!/usr/bin/env python3
"""
Standalone test script for the Generator Agent.
This script connects to the generator MCP server and demonstrates its functionality.
"""
import asyncio
import argparse
import os
import sys
from pathlib import Path
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from prompts.blender import blender_generator_hints, blender_verifier_hints
from prompts.slides import slides_generator_hints, slides_verifier_hints

api_key = os.getenv("OPENAI_API_KEY")

class GeneratorTester:
    def __init__(self):
        self.session = None
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
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print(f"Connected to Generator with tools: {[tool.name for tool in tools]}")

    async def test_generator_workflow(self, args):
        """Test the complete generator workflow."""
        print("\n=== Testing Generator Agent ===")
        
        # 1. Initialize generator
        print("Step 1: Initializing generator...")
        init_result = await self.session.call_tool("initialize_generator", {
            "vision_model": args.vision_model,
            "api_key": api_key,
            "thoughtprocess_save": args.thoughtprocess_save,
            "max_rounds": args.max_rounds,
            "generator_hints": args.generator_hints,
            "init_code": args.init_code,
            "init_image_path": args.init_image_path,
            "target_image_path": args.target_image_path,
            "target_description": args.target_description
        })
        print(f"Initialization result: {init_result.content}")
        
        if not self._is_success(init_result):
            print("Failed to initialize generator")
            return
        
        # 2. Generate initial code
        print("\nStep 2: Generating initial code...")
        gen_result = await self.session.call_tool("generate_code", {})
        print(f"Generation result: {gen_result.content}")
        
        if not self._is_success(gen_result):
            print("Failed to generate initial code")
            return
        
        # 3. Add feedback and generate again
        print("\nStep 3: Adding feedback and generating again...")
        feedback_result = await self.session.call_tool("add_feedback", {
            "feedback": "The code looks good, but please add more comments to explain the logic."
        })
        print(f"Feedback result: {feedback_result.content}")
        
        gen_result2 = await self.session.call_tool("generate_code", {})
        print(f"Second generation result: {gen_result2.content}")
        
        # 4. Save thought process
        print("\nStep 4: Saving thought process...")
        save_result = await self.session.call_tool("save_thought_process", {})
        print(f"Save result: {save_result.content}")
        
        # 5. Get memory
        print("\nStep 5: Getting memory...")
        memory_result = await self.session.call_tool("get_memory", {})
        print(f"Memory length: {len(memory_result.content[0].text) if memory_result.content else 0}")
        
        print("\n=== Generator Test Complete ===")

    def _is_success(self, result):
        """Check if the result indicates success."""
        if result.content and len(result.content) > 0:
            content = result.content[0].text
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
    parser.add_argument("--thoughtprocess-save", default="test_generator_thought.json",
                       help="Path to save thought process")
    parser.add_argument("--max-rounds", type=int, default=5,
                       help="Maximum number of rounds")
    parser.add_argument("--generator-hints", default=blender_generator_hints["shape"],
                       help="Hints for generator")
    initial_code = Path("/home/shaofengyin/AgenticVerifier/data/blendergym/blendshape1/start.py").read_text()
    parser.add_argument("--init-code", default=initial_code,
                       help="Initial code")
    parser.add_argument("--init-image-path", default="/home/shaofengyin/AgenticVerifier/data/blendergym/blendshape1/renders/start",
                       help="Path to initial images")
    parser.add_argument("--target-image-path", default="/home/shaofengyin/AgenticVerifier/data/blendergym/blendshape1/renders/goal",
                       help="Path to target images")
    parser.add_argument("--target-description", default="A simple test scene",
                       help="Target description")
    
    args = parser.parse_args()
    
    # Validate required files
    if not os.path.exists(args.generator_script):
        print(f"Error: Generator script not found: {args.generator_script}")
        sys.exit(1)
    
    tester = GeneratorTester()
    try:
        await tester.connect_to_generator(args.generator_script)
        await tester.test_generator_workflow(args)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())