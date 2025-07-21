import os
import json
import asyncio
from PIL import Image
import io
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
from openai import OpenAI
from mcp.server.fastmcp import FastMCP
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

class ExternalToolClient:
    """Client for connecting to external MCP tool servers (image/scene)."""
    def __init__(self):
        self.sessions = {}  # server_type -> session
        self.exit_stack = AsyncExitStack()
        self.connection_timeout = 30
    async def connect_server(self, server_type: str, server_path: str, api_key: str = None):
        if server_type in self.sessions:
            return
        try:
            env = {"OPENAI_API_KEY": api_key} if api_key else None
            server_params = StdioServerParameters(
                command="python",
                args=[server_path],
                env=env
            )
            stdio_transport = await asyncio.wait_for(
                self.exit_stack.enter_async_context(stdio_client(server_params)),
                timeout=self.connection_timeout
            )
            stdio, write = stdio_transport
            session = await asyncio.wait_for(
                self.exit_stack.enter_async_context(ClientSession(stdio, write)),
                timeout=self.connection_timeout
            )
            await asyncio.wait_for(session.initialize(), timeout=self.connection_timeout)
            response = await asyncio.wait_for(session.list_tools(), timeout=10)
            tools = response.tools
            print(f"Connected to {server_type.capitalize()} server with tools: {[tool.name for tool in tools]}")
            self.sessions[server_type] = session
        except asyncio.TimeoutError:
            raise RuntimeError(f"Failed to connect to {server_type} server: Connection timeout after {self.connection_timeout}s")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to {server_type} server: {str(e)}")
    async def call_tool(self, server_type: str, tool_name: str, tool_args: dict, timeout: int = 60) -> Any:
        session = self.sessions.get(server_type)
        if not session:
            raise RuntimeError(f"{server_type.capitalize()} server not connected")
        try:
            result = await asyncio.wait_for(session.call_tool(tool_name, tool_args), timeout=timeout)
            content = json.loads(result.content[0].text) if result.content else {}
            return content
        except asyncio.TimeoutError:
            raise RuntimeError(f"{server_type.capitalize()} tool call timeout after {timeout}s")
        except Exception as e:
            raise RuntimeError(f"{server_type.capitalize()} tool call failed: {str(e)}")
    async def cleanup(self):
        try:
            await asyncio.wait_for(self.exit_stack.aclose(), timeout=10)
        except asyncio.TimeoutError:
            logging.warning("Cleanup timeout, forcing close")
        except Exception as e:
            logging.warning(f"Cleanup error: {e}")

class VerifierAgent:
    def __init__(self, image_server_path: str = None, scene_server_path: str = None, api_key: str = None):
        self.tool_client = ExternalToolClient()
        self.image_server_path = image_server_path
        self.scene_server_path = scene_server_path
        self.api_key = api_key
        self._tools_connected = False
        self.memory = []
        self.current_round = 0
    async def connect_tools(self):
        if self._tools_connected:
            return
        if self.image_server_path:
            await self.tool_client.connect_server("image", self.image_server_path, self.api_key)
        if self.scene_server_path:
            await self.tool_client.connect_server("scene", self.scene_server_path)
        self._tools_connected = True
    async def exec_image_tool(self, tool_name: str, tool_args: dict, timeout: int = 60):
        await self.connect_tools()
        return await self.tool_client.call_tool("image", tool_name, tool_args, timeout)
    async def exec_scene_tool(self, tool_name: str, tool_args: dict, timeout: int = 60):
        await self.connect_tools()
        return await self.tool_client.call_tool("scene", tool_name, tool_args, timeout)
    async def cleanup(self):
        await self.tool_client.cleanup()

def main():
    mcp = FastMCP("verifier")
    agent_holder = {}

    @mcp.tool()
    async def initialize_verifier(
        mode: str,
        vision_model: str,
        api_key: str,
        thought_save: str,
        task_name: str,
        max_rounds: int = 10,
        target_image_path: str = None,
        target_description: str = None,
        image_server_path: str = "servers/verifier/image.py",
        scene_server_path: str = "servers/verifier/scene.py"
    ) -> dict:
        try:
            agent = VerifierAgent(
                image_server_path=image_server_path,
                scene_server_path=scene_server_path,
                api_key=api_key
            )
            agent_holder['agent'] = agent
            await agent.connect_tools()
            return {"status": "success", "message": "Verifier Agent initialized and tool servers connected"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def exec_pil_code(code: str) -> dict:
        try:
            agent = agent_holder['agent']
            result = await agent.exec_image_tool("exec_pil_code", {"code": code})
            return result
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def compare_images(path1: str, path2: str) -> dict:
        try:
            agent = agent_holder['agent']
            result = await agent.exec_image_tool("compare_images", {"path1": path1, "path2": path2})
            return result
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def get_scene_info(blender_path: str) -> dict:
        try:
            agent = agent_holder['agent']
            result = await agent.exec_scene_tool("get_scene_info", {"blender_path": blender_path})
            return result
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def focus_on_object(blender_path: str, save_dir: str, round_num: int, object_name: str) -> dict:
        try:
            agent = agent_holder['agent']
            result = await agent.exec_scene_tool("focus", {
                "blender_path": blender_path,
                "save_dir": save_dir,
                "round_num": round_num,
                "object_name": object_name
            })
            return result
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def zoom_camera(save_dir: str, direction: str) -> dict:
        try:
            agent = agent_holder['agent']
            result = await agent.exec_scene_tool("zoom", {
                "save_dir": save_dir,
                "direction": direction
            })
            return result
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def move_camera(save_dir: str, direction: str) -> dict:
        try:
            agent = agent_holder['agent']
            result = await agent.exec_scene_tool("move", {
                "save_dir": save_dir,
                "direction": direction
            })
            return result
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def cleanup_verifier() -> dict:
        try:
            agent = agent_holder['agent']
            await agent.cleanup()
            return {"status": "success", "message": "Verifier Agent cleaned up successfully"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    mcp.run(transport="stdio")

if __name__ == "__main__":
    main() 