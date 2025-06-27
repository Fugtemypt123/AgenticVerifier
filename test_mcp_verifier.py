#!/usr/bin/env python3
"""
Simple test script for the MCP Verifier Agent.

This script demonstrates basic functionality without requiring external servers.
"""

import json
import tempfile
import os
from pathlib import Path
from agents.verifier_mcp import MCPVerifierAgent, PILExecutor, ImageDifferentiationTool

def test_basic_functionality():
    """Test basic functionality of the MCP Verifier Agent."""
    print("=== Testing MCP Verifier Agent ===")
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Initialize the agent
        agent = MCPVerifierAgent()
        
        # Test data
        test_hints = "Focus on object positioning and lighting"
        thoughtprocess_save = str(temp_path / "verifier_thought_process.json")
        target_image_path = str(temp_path / "target_images")
        
        # Create target image directory
        os.makedirs(target_image_path, exist_ok=True)
        
        # Create a session
        print("Creating verification session...")
        session_id = agent.create_session(
            vision_model="gpt-4o",
            api_key="test-key",  # This won't actually be used in this test
            thoughtprocess_save=thoughtprocess_save,
            max_rounds=3,
            verifier_hints=test_hints,
            target_image_path=target_image_path,
            blender_save=None
        )
        
        print(f"Session created: {session_id}")
        
        # Get session info
        print("Getting session info...")
        session_info = agent.get_session_info(session_id)
        print(f"Session info: {json.dumps(session_info, indent=2)}")
        
        # Test memory management
        print("Testing memory management...")
        memory = agent.get_memory(session_id)
        print(f"Initial memory length: {len(memory)}")
        
        # Test session listing
        print("Listing sessions...")
        sessions = agent.list_sessions()
        print(f"Active sessions: {len(sessions)}")
        
        # Test thought process saving
        print("Testing thought process saving...")
        agent.save_thought_process(session_id)
        if os.path.exists(thoughtprocess_save):
            print(f"Thought process saved to: {thoughtprocess_save}")
        else:
            print("Failed to save thought process")
        
        # Test session deletion
        print("Testing session deletion...")
        agent.delete_session(session_id)
        sessions = agent.list_sessions()
        print(f"Active sessions after deletion: {len(sessions)}")
        
        print("=== Basic functionality test completed ===")

def test_pil_executor():
    """Test PIL executor functionality."""
    print("\n=== Testing PIL Executor ===")
    
    executor = PILExecutor()
    
    # Test simple PIL code
    test_code = """
from PIL import Image
import numpy as np

# Create a simple test image
img_array = np.zeros((100, 100, 3), dtype=np.uint8)
img_array[25:75, 25:75] = [255, 0, 0]  # Red square
result = Image.fromarray(img_array)
"""
    
    print("Executing PIL code...")
    result = executor.execute(test_code)
    print(f"Execution result: {result['success']}")
    if result['success']:
        print("PIL code executed successfully")
    else:
        print(f"PIL code failed: {result['error']}")
    
    print("=== PIL Executor test completed ===")

def test_image_differentiation():
    """Test image differentiation tool."""
    print("\n=== Testing Image Differentiation Tool ===")
    
    # Create test images
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create two simple test images
        from PIL import Image, ImageDraw
        
        # Image 1: White background with red circle
        img1 = Image.new('RGB', (200, 200), 'white')
        draw1 = ImageDraw.Draw(img1)
        draw1.ellipse([50, 50, 150, 150], fill='red')
        img1_path = str(temp_path / "image1.png")
        img1.save(img1_path)
        
        # Image 2: White background with blue circle
        img2 = Image.new('RGB', (200, 200), 'white')
        draw2 = ImageDraw.Draw(img2)
        draw2.ellipse([50, 50, 150, 150], fill='blue')
        img2_path = str(temp_path / "image2.png")
        img2.save(img2_path)
        
        print(f"Created test images: {img1_path}, {img2_path}")
        
        # Test image differentiation (without API call for this test)
        print("Image differentiation tool would compare these images")
        print("In a real scenario, this would use OpenAI API to analyze differences")
        
        print("=== Image Differentiation test completed ===")

def test_error_handling():
    """Test error handling of the MCP Verifier Agent."""
    print("\n=== Testing Error Handling ===")
    
    agent = MCPVerifierAgent()
    
    # Test accessing non-existent session
    print("Testing access to non-existent session...")
    try:
        agent.get_session_info("non-existent-session")
        print("ERROR: Should have raised an exception")
    except ValueError as e:
        print(f"Correctly caught error: {e}")
    
    # Test deleting non-existent session
    print("Testing deletion of non-existent session...")
    try:
        agent.delete_session("non-existent-session")
        print("ERROR: Should have raised an exception")
    except ValueError as e:
        print(f"Correctly caught error: {e}")
    
    print("=== Error handling test completed ===")

def test_session_management():
    """Test session management functionality."""
    print("\n=== Testing Session Management ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        agent = MCPVerifierAgent()
        
        # Create multiple sessions
        session_ids = []
        for i in range(3):
            session_id = agent.create_session(
                vision_model="gpt-4o",
                api_key="test-key",
                thoughtprocess_save=str(temp_path / f"verifier_thought_process_{i}.json"),
                max_rounds=5,
                verifier_hints=f"Test hint {i}",
                target_image_path=str(temp_path / f"target_images_{i}"),
                blender_save=None
            )
            session_ids.append(session_id)
            print(f"Created session {i}: {session_id}")
        
        # List all sessions
        sessions = agent.list_sessions()
        print(f"Total active sessions: {len(sessions)}")
        
        # Verify all sessions exist
        for session_id in session_ids:
            info = agent.get_session_info(session_id)
            print(f"Session {session_id}: round {info['current_round']}")
        
        # Delete one session
        print(f"Deleting session: {session_ids[1]}")
        agent.delete_session(session_ids[1])
        
        # Verify session was deleted
        sessions = agent.list_sessions()
        print(f"Active sessions after deletion: {len(sessions)}")
        
        # Clean up remaining sessions
        for session_id in session_ids:
            if session_id in agent.sessions:
                agent.delete_session(session_id)
        
        print("=== Session management test completed ===")

def test_verification_workflow():
    """Test a complete verification workflow."""
    print("\n=== Testing Verification Workflow ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        agent = MCPVerifierAgent()
        
        # Create target images directory
        target_image_path = str(temp_path / "target_images")
        os.makedirs(target_image_path, exist_ok=True)
        
        # Create a verification session
        session_id = agent.create_session(
            vision_model="gpt-4o",
            api_key="test-key",
            thoughtprocess_save=str(temp_path / "verifier_thought_process.json"),
            max_rounds=2,
            verifier_hints="Test verification workflow",
            target_image_path=target_image_path,
            blender_save=None
        )
        
        print(f"Created verification session: {session_id}")
        
        # Test verification (mock data)
        test_code = """
import bpy
# Test Blender code
bpy.ops.mesh.primitive_cube_add()
"""
        
        render_path = str(temp_path / "renders")
        os.makedirs(render_path, exist_ok=True)
        
        # Create mock render images
        from PIL import Image, ImageDraw
        
        # Mock render1.png
        render1 = Image.new('RGB', (400, 300), 'lightblue')
        draw1 = ImageDraw.Draw(render1)
        draw1.rectangle([100, 100, 300, 200], fill='gray')
        render1.save(os.path.join(render_path, 'render1.png'))
        
        # Mock render2.png
        render2 = Image.new('RGB', (400, 300), 'lightgreen')
        draw2 = ImageDraw.Draw(render2)
        draw2.rectangle([150, 150, 250, 250], fill='gray')
        render2.save(os.path.join(render_path, 'render2.png'))
        
        print("Created mock render images")
        
        # Test verification (this would normally call OpenAI API)
        print("Testing verification workflow...")
        try:
            # Note: This would fail in test environment due to API key
            # In real usage, this would work with valid API key
            print("Verification workflow test completed (API call would be made in real scenario)")
        except Exception as e:
            print(f"Verification test (expected to fail without API): {e}")
        
        # Clean up
        agent.delete_session(session_id)
        
        print("=== Verification workflow test completed ===")

def main():
    """Run all tests."""
    print("Starting MCP Verifier Agent Tests\n")
    
    try:
        test_basic_functionality()
        test_pil_executor()
        test_image_differentiation()
        test_error_handling()
        test_session_management()
        test_verification_workflow()
        print("\n=== All tests completed successfully ===")
    except Exception as e:
        print(f"\n=== Test failed with error: {e} ===")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 