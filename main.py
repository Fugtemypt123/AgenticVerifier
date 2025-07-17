 #!/usr/bin/env python3
"""
Main entry for dual-agent interactive framework (generator/verifier).
Supports 3D (Blender) and 2D (PPTX) modes.
Uses MCP stdio connections instead of HTTP servers.
"""
import argparse
import os
import sys
import time
import json
import asyncio
from pathlib import Path
from typing import Optional
from contextlib import AsyncExitStack
import requests
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

api_key = os.getenv("OPENAI_API_KEY")

# ========== Agent Client Wrappers ==========

class GeneratorAgentClient:
    def __init__(self, script_path: str):
        self.script_path = script_path
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.initialized = False

    async def connect(self):
        """Connect to the Generator MCP server."""
        server_params = StdioServerParameters(
            command="python",
            args=[self.script_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        print(f"Connected to Generator: {self.script_path}")

    async def create_session(self, **kwargs):
        """Initialize the generator with session parameters."""
        if not self.session:
            raise RuntimeError("Not connected. Call connect() first.")
        
        result = await self.session.call_tool("initialize_generator", kwargs)
        if result.content and len(result.content) > 0:
            content = result.content[0].text
            if '"status": "success"' in content or '"status":"success"' in content:
                self.initialized = True
                return "success"
        raise RuntimeError(f"Failed to create session: {result.content}")

    async def generate_code(self, feedback: Optional[str] = None):
        """Generate code, optionally with feedback."""
        if not self.initialized:
            raise RuntimeError("Generator not initialized. Call create_session() first.")
        
        params = {}
        if feedback:
            params["feedback"] = feedback
        
        result = await self.session.call_tool("generate_code", params)
        if result.content and len(result.content) > 0:
            content = result.content[0].text
            return json.loads(content)
        raise RuntimeError(f"Failed to generate code: {result.content}")

    async def add_feedback(self, feedback: str):
        """Add feedback to the generator."""
        if not self.initialized:
            raise RuntimeError("Generator not initialized. Call create_session() first.")
        
        result = await self.session.call_tool("add_feedback", {"feedback": feedback})
        if not (result.content and len(result.content) > 0 and 
                ('"status": "success"' in result.content[0].text or '"status":"success"' in result.content[0].text)):
            raise RuntimeError(f"Failed to add feedback: {result.content}")

    async def save_thought_process(self):
        """Save the thought process."""
        if not self.initialized:
            raise RuntimeError("Generator not initialized. Call create_session() first.")
        
        result = await self.session.call_tool("save_thought_process", {})
        if not (result.content and len(result.content) > 0 and 
                ('"status": "success"' in result.content[0].text or '"status":"success"' in result.content[0].text)):
            raise RuntimeError(f"Failed to save thought process: {result.content}")

    async def cleanup(self):
        """Clean up resources."""
        await self.exit_stack.aclose()


class VerifierAgentClient:
    def __init__(self, script_path: str):
        self.script_path = script_path
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.initialized = False

    async def connect(self):
        """Connect to the Verifier MCP server."""
        server_params = StdioServerParameters(
            command="python",
            args=[self.script_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        print(f"Connected to Verifier: {self.script_path}")

    async def create_session(self, **kwargs):
        """Initialize the verifier with session parameters."""
        if not self.session:
            raise RuntimeError("Not connected. Call connect() first.")
        
        result = await self.session.call_tool("initialize_verifier", kwargs)
        if result.content and len(result.content) > 0:
            content = result.content[0].text
            if '"status": "success"' in content or '"status":"success"' in content:
                self.initialized = True
                return "success"
        raise RuntimeError(f"Failed to create session: {result.content}")

    async def verify_scene(self, code: str, render_path: str, round_num: int):
        """Verify the scene with given parameters."""
        if not self.initialized:
            raise RuntimeError("Verifier not initialized. Call create_session() first.")
        
        result = await self.session.call_tool("verify_scene", {
            "code": code,
            "render_path": render_path,
            "round_num": round_num
        })
        if result.content and len(result.content) > 0:
            content = result.content[0].text
            return json.loads(content)
        raise RuntimeError(f"Failed to verify scene: {result.content}")

    async def save_thought_process(self):
        """Save the thought process."""
        if not self.initialized:
            raise RuntimeError("Verifier not initialized. Call create_session() first.")
        
        result = await self.session.call_tool("save_thought_process", {})
        if not (result.content and len(result.content) > 0 and 
                ('"status": "success"' in result.content[0].text or '"status":"success"' in result.content[0].text)):
            raise RuntimeError(f"Failed to save thought process: {result.content}")

    async def cleanup(self):
        """Clean up resources."""
        await self.exit_stack.aclose()

# ========== Executor Wrappers ==========

class BlenderExecutorClient:
    def __init__(self, url: str):
        self.url = url
    def execute(self, code: str, round_num: int, **kwargs):
        resp = requests.post(f"{self.url}/exec_script", json={"code": code, "round": round_num, **kwargs})
        resp.raise_for_status()
        return resp.json()

class SlidesExecutorClient:
    def __init__(self, url: str):
        self.url = url
    def execute(self, code: str, round_num: int, code_save: str):
        resp = requests.post(f"{self.url}/exec_pptx", json={"code": code, "round": round_num, "code_save": code_save})
        resp.raise_for_status()
        return resp.json()

# ========== Main Dual-Agent Loop ==========

async def main():
    parser = argparse.ArgumentParser(description="Dual-agent interactive framework")
    parser.add_argument("--mode", choices=["3d", "2d"], required=True, help="Choose 3D (Blender) or 2D (PPTX) mode")
    parser.add_argument("--vision-model", default="gpt-4o", help="OpenAI vision model")
    parser.add_argument("--max-rounds", type=int, default=10, help="Max interaction rounds")
    parser.add_argument("--init-code", required=True, help="Path to initial code file")
    parser.add_argument("--init-image-path", default=None, help="Path to initial images")
    parser.add_argument("--target-image-path", default=None, help="Path to target images")
    parser.add_argument("--generator-hints", default=None, help="Hints for generator agent")
    parser.add_argument("--verifier-hints", default=None, help="Hints for verifier agent")
    parser.add_argument("--thoughtprocess-save", default="thought_process.json", help="Path to save generator thought process")
    parser.add_argument("--verifier-thoughtprocess-save", default="verifier_thought_process.json", help="Path to save verifier thought process")
    parser.add_argument("--render-save", default="renders", help="Render save directory")
    parser.add_argument("--code-save", default="slides_code", help="Slides code save directory (2D mode)")
    parser.add_argument("--blender-save", default=None, help="Blender save path (3D mode)")
    parser.add_argument("--generator-script", default="agents/generator_mcp.py", help="Generator MCP script path")
    parser.add_argument("--verifier-script", default="agents/verifier_mcp.py", help="Verifier MCP script path")
    parser.add_argument("--blender-url", default="http://localhost:8001", help="Blender executor server URL")
    parser.add_argument("--slides-url", default="http://localhost:8002", help="Slides executor server URL")
    args = parser.parse_args()

    # Read initial code
    with open(args.init_code, 'r') as f:
        init_code = f.read()

    # Prepare output dirs
    os.makedirs("output", exist_ok=True)
    os.makedirs(args.render_save, exist_ok=True)
    if args.mode == "2d":
        os.makedirs(args.code_save, exist_ok=True)

    # Init agents
    generator = GeneratorAgentClient(args.generator_script)
    verifier = VerifierAgentClient(args.verifier_script)

    try:
        # Connect to agents
        await generator.connect()
        await verifier.connect()

        # Create sessions
        await generator.create_session(
            vision_model=args.vision_model,
            api_key=api_key,
            thoughtprocess_save=args.thoughtprocess_save,
            max_rounds=args.max_rounds,
            generator_hints=args.generator_hints,
            init_code=init_code,
            init_image_path=args.init_image_path,
            target_image_path=args.target_image_path,
            target_description=None
        )
        await verifier.create_session(
            vision_model=args.vision_model,
            api_key=api_key,
            thoughtprocess_save=args.verifier_thoughtprocess_save,
            max_rounds=args.max_rounds,
            verifier_hints=args.verifier_hints,
            target_image_path=args.target_image_path,
            blender_save=args.blender_save
        )

        # Init executors (still HTTP-based)
        if args.mode == "3d":
            executor = BlenderExecutorClient(args.blender_url)
        else:
            executor = SlidesExecutorClient(args.slides_url)

        # Main loop
        for round_num in range(args.max_rounds):
            print(f"\n=== Round {round_num+1} ===")
            
            # 1. Generator生成代码
            gen_result = await generator.generate_code()
            if gen_result.get("status") == "max_rounds_reached":
                print("Max rounds reached. Stopping.")
                break
            if gen_result.get("status") == "error":
                print(f"Generator error: {gen_result['error']}")
                break
            code = gen_result["code"]
            print(f"Generated code (truncated):\n{code[:200]}...")
            
            # 2. 执行代码
            if args.mode == "3d":
                exec_result = executor.execute(
                    code=code,
                    round_num=round_num,
                    blender_command="blender",
                    blender_file="scene.blend",
                    blender_script="render_script.py",
                    script_save="scripts",
                    render_save=args.render_save,
                    blender_save=args.blender_save
                )
            else:
                exec_result = executor.execute(
                    code=code,
                    round_num=round_num,
                    code_save=args.code_save
                )
            
            if exec_result.get("status") != "success":
                print(f"Execution failed: {exec_result.get('output')}")
                await generator.add_feedback(f"Execution error: {exec_result.get('output')}")
                continue
            
            # 3. Verifier验证
            if args.mode == "3d":
                verify_result = await verifier.verify_scene(
                    code=code,
                    render_path=args.render_save,
                    round_num=round_num
                )
            else:
                # 2D模式可扩展为pptx图片路径
                verify_result = await verifier.verify_scene(
                    code=code,
                    render_path=args.code_save,
                    round_num=round_num
                )
            
            print(f"Verifier result: {verify_result.get('status')}")
            if verify_result.get("status") == "end":
                print("Verifier: OK! Task complete.")
                break
            elif verify_result.get("status") == "continue":
                feedback = verify_result["output"]
                print(f"Verifier feedback: {feedback}")
                await generator.add_feedback(feedback)
            else:
                print(f"Verifier error: {verify_result.get('error')}")
                break
            
            # 4. 保存思考过程
            await generator.save_thought_process()
            await verifier.save_thought_process()
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        # Cleanup
        await generator.cleanup()
        await verifier.cleanup()
    
    print("\n=== Dual-agent interaction finished ===")

if __name__ == "__main__":
    asyncio.run(main())