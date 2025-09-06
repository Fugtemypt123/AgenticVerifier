#!/usr/bin/env python3
"""
Test script for Design2Code mode.
This script demonstrates how to use the new design2code mode.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from main import main

async def test_design2code():
    """Test the design2code mode with example data."""
    
    # Set up test parameters
    test_args = [
        "--mode", "design2code",
        "--vision-model", "gpt-4o",
        "--api-key", os.getenv("OPENAI_API_KEY", ""),
        "--max-rounds", "3",
        "--init-image-path", "data/design2code/example/design.png",
        "--target-description", "data/design2code/example/description.txt",
        "--output-dir", "output/design2code_test",
        "--task-name", "landing_page",
        "--generator-script", "agents/generator_mcp.py",
        "--verifier-script", "agents/verifier_mcp.py",
        "--html-server-path", "servers/generator/html.py",
        "--web-server-path", "servers/verifier/web.py",
        "--browser-command", "google-chrome"
    ]
    
    # Override sys.argv for the main function
    original_argv = sys.argv
    sys.argv = ["test_design2code.py"] + test_args
    
    try:
        print("🚀 Starting Design2Code test...")
        print(f"📁 Output directory: output/design2code_test")
        print(f"🖼️  Design image: data/design2code/example/design.png")
        print(f"📝 Description: data/design2code/example/description.txt")
        print(f"🔄 Max rounds: 3")
        print("=" * 50)
        
        await main()
        
        print("=" * 50)
        print("✅ Design2Code test completed!")
        print("📁 Check the output directory for generated HTML files and screenshots")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore original argv
        sys.argv = original_argv

def create_test_design():
    """Create a simple test design image if it doesn't exist."""
    design_path = Path("data/design2code/example/design.png")
    
    if not design_path.exists() or design_path.stat().st_size < 1000:
        print("🎨 Creating a simple test design image...")
        
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a simple landing page design
            width, height = 1200, 800
            img = Image.new('RGB', (width, height), color='white')
            draw = ImageDraw.Draw(img)
            
            # Header
            draw.rectangle([0, 0, width, 80], fill='#2c3e50')
            draw.text((50, 30), "MyCompany", fill='white', font_size=24)
            draw.text((width-200, 30), "Home About Contact", fill='white', font_size=16)
            
            # Hero section
            draw.rectangle([0, 80, width, 400], fill='#3498db')
            draw.text((width//2-200, 200), "Welcome to Our Amazing Product", fill='white', font_size=32)
            draw.text((width//2-150, 250), "Build something incredible today", fill='white', font_size=18)
            draw.rectangle([width//2-100, 300, width//2+100, 350], fill='#e74c3c')
            draw.text((width//2-30, 315), "Get Started", fill='white', font_size=16)
            
            # Features section
            draw.rectangle([0, 400, width, 600], fill='#ecf0f1')
            draw.text((100, 450), "Feature 1", fill='#2c3e50', font_size=20)
            draw.text((100, 480), "Amazing feature description", fill='#7f8c8d', font_size=14)
            
            draw.text((400, 450), "Feature 2", fill='#2c3e50', font_size=20)
            draw.text((400, 480), "Another great feature", fill='#7f8c8d', font_size=14)
            
            draw.text((700, 450), "Feature 3", fill='#2c3e50', font_size=20)
            draw.text((700, 480), "Third awesome feature", fill='#7f8c8d', font_size=14)
            
            # Footer
            draw.rectangle([0, 600, width, height], fill='#34495e')
            draw.text((50, 650), "© 2024 MyCompany. All rights reserved.", fill='white', font_size=14)
            draw.text((width-200, 650), "Contact: info@mycompany.com", fill='white', font_size=14)
            
            # Save the image
            design_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(design_path, 'PNG')
            print(f"✅ Created test design: {design_path}")
            
        except ImportError:
            print("⚠️  PIL not available, using placeholder design file")
            # Create a simple placeholder
            design_path.parent.mkdir(parents=True, exist_ok=True)
            with open(design_path, 'w') as f:
                f.write("# Placeholder design image\n")
        except Exception as e:
            print(f"⚠️  Could not create design image: {e}")

if __name__ == "__main__":
    # Create test design if needed
    create_test_design()
    
    # Check if API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY environment variable not set")
        print("   Please set your OpenAI API key to run the test")
        print("   export OPENAI_API_KEY='your-api-key-here'")
        sys.exit(1)
    
    # Run the test
    asyncio.run(test_design2code())
