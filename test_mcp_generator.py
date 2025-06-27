#!/usr/bin/env python3
"""
Simple test script for the MCP Generator Agent.

This script demonstrates basic functionality without requiring external servers.
"""

import json
import tempfile
import os
from pathlib import Path
from agents.generator_mcp_advanced import AdvancedGeneratorAgent

def test_basic_functionality():
    """Test basic functionality of the Advanced Generator Agent."""
    print("=== Testing Advanced Generator Agent ===")
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Initialize the agent
        agent = AdvancedGeneratorAgent()
        
        # Test data
        test_init_code = """
import bpy

# Clear existing objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Create a simple cube
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
cube = bpy.context.active_object
cube.name = "TestCube"

# Add a material
material = bpy.data.materials.new(name="TestMaterial")
material.use_nodes = True
cube.data.materials.append(material)
"""
        
        test_hints = "Add a sphere next to the cube"
        thoughtprocess_save = str(temp_path / "thought_process.json")
        
        # Create a session
        print("Creating session...")
        session_id = agent.create_session(
            vision_model="gpt-4o",
            api_key="test-key",  # This won't actually be used in this test
            thoughtprocess_save=thoughtprocess_save,
            max_rounds=3,
            generator_hints=test_hints,
            init_code=test_init_code,
            init_image_path=None,  # No images for this test
            target_image_path=None,
            target_description="A scene with a cube and a sphere"
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
        
        # Add some feedback
        print("Adding feedback...")
        agent.add_feedback(session_id, "The cube looks good, but we need a sphere")
        
        # Get updated memory
        memory = agent.get_memory(session_id)
        print(f"Memory length after feedback: {len(memory)}")
        
        # Test session listing
        print("Listing sessions...")
        sessions = agent.list_sessions()
        print(f"Active sessions: {len(sessions)}")
        
        # Test memory reset
        print("Testing memory reset...")
        agent.reset_session_memory(session_id)
        memory = agent.get_memory(session_id)
        print(f"Memory length after reset: {len(memory)}")
        
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

def test_error_handling():
    """Test error handling of the Advanced Generator Agent."""
    print("\n=== Testing Error Handling ===")
    
    agent = AdvancedGeneratorAgent()
    
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
        agent = AdvancedGeneratorAgent()
        
        # Create multiple sessions
        session_ids = []
        for i in range(3):
            session_id = agent.create_session(
                vision_model="gpt-4o",
                api_key="test-key",
                thoughtprocess_save=str(temp_path / f"thought_process_{i}.json"),
                max_rounds=5,
                generator_hints=f"Test hint {i}",
                init_code=f"# Test code {i}",
                init_image_path=None,
                target_image_path=None,
                target_description=f"Test target {i}"
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

def main():
    """Run all tests."""
    print("Starting MCP Generator Agent Tests\n")
    
    try:
        test_basic_functionality()
        test_error_handling()
        test_session_management()
        print("\n=== All tests completed successfully ===")
    except Exception as e:
        print(f"\n=== Test failed with error: {e} ===")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 