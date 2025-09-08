#!/usr/bin/env python3
"""
Evaluation script for AgenticVerifier Design2Code results.
Implements the 5 core metrics from Design2Code: Block, Text, Position, Color, and CLIP.
"""

import os
import sys
import argparse
import json
import re
import math
from PIL import Image
from tqdm import tqdm
import numpy as np
import torch
from torchvision.transforms import Compose, Resize, CenterCrop, ToTensor, Normalize
from transformers import CLIPProcessor, CLIPModel
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import tempfile
import shutil
from collections import defaultdict

# Global CLIP model/processor to share across threads
GLOBAL_CLIP_MODEL = None
GLOBAL_CLIP_PROCESSOR = None


def ensure_clip_loaded():
    """
    Lazily load the global CLIP model and processor once per process.
    """
    global GLOBAL_CLIP_MODEL, GLOBAL_CLIP_PROCESSOR
    if GLOBAL_CLIP_MODEL is None or GLOBAL_CLIP_PROCESSOR is None:
        GLOBAL_CLIP_MODEL = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        GLOBAL_CLIP_PROCESSOR = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")


def clip_similarity(image1, image2):
    """
    Compute the CLIP similarity between two PIL images.

    Args:
    image1 (PIL.Image): The first input image.
    image2 (PIL.Image): The second input image.

    Returns:
    float: The CLIP similarity between the two images.
    """
    if image1.size != image2.size:
        image2 = image2.resize(image1.size)

    # Ensure global model is initialized
    ensure_clip_loaded()

    # Preprocess the images
    images = [image1, image2]
    inputs = GLOBAL_CLIP_PROCESSOR(images=images, return_tensors="pt")

    # Compute the features for the images
    with torch.no_grad():
        features = GLOBAL_CLIP_MODEL.get_image_features(**inputs)

    # Compute the cosine similarity between the image features
    sim = torch.nn.functional.cosine_similarity(features[0], features[1], dim=-1)

    return sim.item()


def photometric_loss(image1: Image.Image, image2: Image.Image) -> float:
    """
    Compute the photometric loss between two PIL images.

    Args:
    image1 (PIL.Image): The first input image.
    image2 (PIL.Image): The second input image.

    Returns:
    float: The photometric loss between the two images.
    """
    if image1.size != image2.size:
        image2 = image2.resize(image1.size)
    
    # Convert images to numpy arrays
    img1_array = np.array(image1)[:, :, :3]
    img2_array = np.array(image2)[:, :, :3]

    # Normalize images to [0, 1]
    img1_norm = img1_array.astype(np.float32) / 255.0
    img2_norm = img2_array.astype(np.float32) / 255.0

    # Compute the squared difference between the normalized images
    diff = np.square(img1_norm - img2_norm)

    # Compute the mean squared error
    mse = np.mean(diff)
    return mse


def parse_html_and_css(html_content: str) -> dict:
    """
    Parse HTML content and extract CSS information.
    
    Args:
        html_content (str): HTML content to analyze
        
    Returns:
        dict: Parsed HTML structure and CSS information
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract CSS from style tags and inline styles
        css_rules = []
        inline_styles = []
        
        # Extract from <style> tags
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                css_rules.append(style_tag.string)
        
        # Extract inline styles
        for element in soup.find_all(style=True):
            inline_styles.append(element['style'])
        
        # Parse CSS rules
        css_properties = defaultdict(list)
        for css_text in css_rules + inline_styles:
            # Simple CSS parsing (can be enhanced)
            properties = re.findall(r'([a-zA-Z-]+)\s*:\s*([^;]+)', css_text)
            for prop, value in properties:
                css_properties[prop.strip()].append(value.strip())
        
        return {
            'soup': soup,
            'css_properties': dict(css_properties),
            'elements': soup.find_all(),
            'block_elements': soup.find_all(['div', 'section', 'article', 'header', 'footer', 'main', 'aside', 'nav']),
            'text_elements': soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'a', 'button', 'label'])
        }
    except ImportError:
        # Fallback without BeautifulSoup
        return {
            'soup': None,
            'css_properties': {},
            'elements': [],
            'block_elements': [],
            'text_elements': []
        }


def block_metric(html1: str, html2: str) -> float:
    """
    Block metric: Compare block-level elements structure.
    
    Args:
        html1 (str): First HTML content
        html2 (str): Second HTML content
        
    Returns:
        float: Block similarity score (0-1, higher is more similar)
    """
    try:
        parsed1 = parse_html_and_css(html1)
        parsed2 = parse_html_and_css(html2)
        
        blocks1 = parsed1['block_elements']
        blocks2 = parsed2['block_elements']
        
        # Count block elements
        block_count1 = len(blocks1)
        block_count2 = len(blocks2)
        
        # Calculate block type distribution
        block_types1 = defaultdict(int)
        block_types2 = defaultdict(int)
        
        for block in blocks1:
            block_types1[block.name] += 1
        for block in blocks2:
            block_types2[block.name] += 1
        
        # Calculate similarity based on count and type distribution
        count_similarity = 1.0 - abs(block_count1 - block_count2) / max(block_count1, block_count2, 1)
        
        # Type distribution similarity
        all_types = set(block_types1.keys()) | set(block_types2.keys())
        type_similarity = 0.0
        if all_types:
            for block_type in all_types:
                count1 = block_types1.get(block_type, 0)
                count2 = block_types2.get(block_type, 0)
                max_count = max(count1, count2, 1)
                type_similarity += 1.0 - abs(count1 - count2) / max_count
            type_similarity /= len(all_types)
        
        # Weighted combination
        block_similarity = 0.6 * count_similarity + 0.4 * type_similarity
        return max(0.0, min(1.0, block_similarity))
        
    except Exception as e:
        print(f"Error computing block metric: {e}")
        return 0.0


def text_metric(html1: str, html2: str) -> float:
    """
    Text metric: Compare text content and styling.
    
    Args:
        html1 (str): First HTML content
        html2 (str): Second HTML content
        
    Returns:
        float: Text similarity score (0-1, higher is more similar)
    """
    try:
        parsed1 = parse_html_and_css(html1)
        parsed2 = parse_html_and_css(html2)
        
        # Extract text content
        def extract_text_content(parsed):
            text_elements = parsed['text_elements']
            texts = []
            for element in text_elements:
                text = element.get_text(strip=True)
                if text:
                    texts.append(text)
            return texts
        
        texts1 = extract_text_content(parsed1)
        texts2 = extract_text_content(parsed2)
        
        # Text content similarity using simple matching
        if not texts1 and not texts2:
            return 1.0
        if not texts1 or not texts2:
            return 0.0
        
        # Calculate text similarity
        matched_texts = 0
        for text1 in texts1:
            for text2 in texts2:
                if text1.lower().strip() == text2.lower().strip():
                    matched_texts += 1
                    break
        
        text_content_similarity = matched_texts / max(len(texts1), len(texts2))
        
        # Text styling similarity (font-size, font-family, etc.)
        font_props1 = parsed1['css_properties']
        font_props2 = parsed2['css_properties']
        
        font_keys = ['font-size', 'font-family', 'font-weight', 'color']
        style_similarity = 0.0
        for key in font_keys:
            values1 = set(font_props1.get(key, []))
            values2 = set(font_props2.get(key, []))
            if values1 or values2:
                intersection = len(values1 & values2)
                union = len(values1 | values2)
                style_similarity += intersection / union if union > 0 else 0.0
        
        style_similarity /= len(font_keys)
        
        # Weighted combination
        text_similarity = 0.7 * text_content_similarity + 0.3 * style_similarity
        return max(0.0, min(1.0, text_similarity))
        
    except Exception as e:
        print(f"Error computing text metric: {e}")
        return 0.0


def position_metric(html1: str, html2: str) -> float:
    """
    Position metric: Compare element positioning.
    
    Args:
        html1 (str): First HTML content
        html2 (str): Second HTML content
        
    Returns:
        float: Position similarity score (0-1, higher is more similar)
    """
    try:
        parsed1 = parse_html_and_css(html1)
        parsed2 = parse_html_and_css(html2)
        
        # Extract positioning properties
        def extract_positioning(parsed):
            css_props = parsed['css_properties']
            positioning = {
                'position': css_props.get('position', []),
                'top': css_props.get('top', []),
                'left': css_props.get('left', []),
                'right': css_props.get('right', []),
                'bottom': css_props.get('bottom', []),
                'margin': css_props.get('margin', []),
                'padding': css_props.get('padding', []),
                'width': css_props.get('width', []),
                'height': css_props.get('height', [])
            }
            return positioning
        
        pos1 = extract_positioning(parsed1)
        pos2 = extract_positioning(parsed2)
        
        # Calculate position similarity
        position_similarity = 0.0
        position_keys = ['position', 'top', 'left', 'right', 'bottom', 'margin', 'padding', 'width', 'height']
        
        for key in position_keys:
            values1 = set(pos1.get(key, []))
            values2 = set(pos2.get(key, []))
            if values1 or values2:
                intersection = len(values1 & values2)
                union = len(values1 | values2)
                position_similarity += intersection / union if union > 0 else 0.0
        
        position_similarity /= len(position_keys)
        return max(0.0, min(1.0, position_similarity))
        
    except Exception as e:
        print(f"Error computing position metric: {e}")
        return 0.0


def color_metric(html1: str, html2: str) -> float:
    """
    Color metric: Compare color properties.
    
    Args:
        html1 (str): First HTML content
        html2 (str): Second HTML content
        
    Returns:
        float: Color similarity score (0-1, higher is more similar)
    """
    try:
        parsed1 = parse_html_and_css(html1)
        parsed2 = parse_html_and_css(html2)
        
        def extract_colors(parsed):
            css_props = parsed['css_properties']
            colors = []
            
            # Extract color properties
            color_props = ['color', 'background-color', 'border-color']
            for prop in color_props:
                colors.extend(css_props.get(prop, []))
            
            # Parse color values
            parsed_colors = []
            for color in colors:
                rgb = parse_color_to_rgb(color)
                if rgb:
                    parsed_colors.append(rgb)
            
            return parsed_colors
        
        colors1 = extract_colors(parsed1)
        colors2 = extract_colors(parsed2)
        
        if not colors1 and not colors2:
            return 1.0
        if not colors1 or not colors2:
            return 0.0
        
        # Calculate color similarity using RGB distance
        color_similarities = []
        for color1 in colors1:
            best_similarity = 0.0
            for color2 in colors2:
                similarity = calculate_color_similarity(color1, color2)
                best_similarity = max(best_similarity, similarity)
            color_similarities.append(best_similarity)
        
        avg_similarity = sum(color_similarities) / len(color_similarities)
        return max(0.0, min(1.0, avg_similarity))
        
    except Exception as e:
        print(f"Error computing color metric: {e}")
        return 0.0


def parse_color_to_rgb(color_str: str) -> tuple:
    """Parse color string to RGB tuple."""
    try:
        color_str = color_str.strip().lower()
        
        # Handle hex colors
        if color_str.startswith('#'):
            hex_color = color_str[1:]
            if len(hex_color) == 3:
                hex_color = ''.join([c*2 for c in hex_color])
            if len(hex_color) == 6:
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        # Handle rgb() colors
        if color_str.startswith('rgb('):
            rgb_match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', color_str)
            if rgb_match:
                return tuple(int(x) for x in rgb_match.groups())
        
        # Handle rgba() colors
        if color_str.startswith('rgba('):
            rgba_match = re.search(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*[\d.]+\)', color_str)
            if rgba_match:
                return tuple(int(x) for x in rgba_match.groups()[:3])
        
        # Handle named colors (basic set)
        named_colors = {
            'red': (255, 0, 0), 'green': (0, 128, 0), 'blue': (0, 0, 255),
            'white': (255, 255, 255), 'black': (0, 0, 0), 'gray': (128, 128, 128),
            'yellow': (255, 255, 0), 'orange': (255, 165, 0), 'purple': (128, 0, 128)
        }
        if color_str in named_colors:
            return named_colors[color_str]
        
        return None
    except:
        return None


def calculate_color_similarity(rgb1: tuple, rgb2: tuple) -> float:
    """Calculate color similarity using Euclidean distance in RGB space."""
    try:
        distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(rgb1, rgb2)))
        max_distance = math.sqrt(3 * 255 ** 2)  # Maximum possible distance
        similarity = 1.0 - (distance / max_distance)
        return max(0.0, min(1.0, similarity))
    except:
        return 0.0


def render_html_to_image(html_content: str, output_path: str, width: int = 1024, height: int = 768) -> bool:
    """
    Render HTML content to an image using a headless browser.
    
    Args:
        html_content (str): HTML content to render
        output_path (str): Path to save the rendered image
        width (int): Image width
        height (int): Image height
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Try using playwright first
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': width, 'height': height})
                page.set_content(html_content)
                page.screenshot(path=output_path, full_page=True)
                browser.close()
                return True
        except ImportError:
            pass
        
        # Fallback to selenium
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument(f'--window-size={width},{height}')
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(f"data:text/html,{html_content}")
            driver.save_screenshot(output_path)
            driver.quit()
            return True
        except ImportError:
            pass
        
        # Last resort: try wkhtmltoimage
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                f.write(html_content)
                temp_html = f.name
            
            cmd = [
                'wkhtmltoimage',
                '--width', str(width),
                '--height', str(height),
                '--format', 'png',
                temp_html,
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            os.unlink(temp_html)
            return result.returncode == 0
            
        except Exception:
            pass
        
        return False
        
    except Exception as e:
        print(f"Error rendering HTML to image: {e}")
        return False


def process_design2code_instance(output_base_dir: str, task_dir: str):
    """
    Process a single Design2Code task instance directory and compute metrics across rounds.
    Implements the 5 core metrics: Block, Text, Position, Color, and CLIP.

    Returns:
        tuple: (task_dir, task_instance_scores, best_scores)
               where best_scores is a dict with the 5 metrics
    """
    task_instance_dir = os.path.join(output_base_dir, task_dir)
    renders_dir = os.path.join(task_instance_dir, "renders")
    html_dir = os.path.join(task_instance_dir, "html")

    if not os.path.exists(renders_dir) or not os.path.exists(html_dir):
        return task_dir, {}, None

    # Look for ground truth files
    gt_renders_dir = f"data/design2code/{task_dir}/renders/goal"
    gt_html_dir = f"data/design2code/{task_dir}/html/goal"
    
    if not os.path.exists(gt_renders_dir) or not os.path.exists(gt_html_dir):
        return task_dir, {}, None

    task_instance_scores = {}

    # Get all round directories (1, 2, 3, 4, etc.)
    round_dirs = [d for d in os.listdir(renders_dir)
                 if os.path.isdir(os.path.join(renders_dir, d))]
    try:
        round_dirs.sort(key=lambda x: int(x))
    except Exception:
        # Fallback to lexical sort if non-numeric dirs exist
        round_dirs.sort()

    if not round_dirs:
        return task_dir, {}, None

    for round_dir in round_dirs:
        round_path = os.path.join(renders_dir, round_dir)
        html_round_path = os.path.join(html_dir, round_dir)
        task_instance_scores[round_dir] = {}

        # Collect all metric scores for this round
        block_scores = []
        text_scores = []
        position_scores = []
        color_scores = []
        clip_scores = []

        # Process render1
        render1_path = os.path.join(round_path, "render1.png")
        gt_render1_path = os.path.join(gt_renders_dir, "render1.png")
        html1_path = os.path.join(html_round_path, "render1.html")
        gt_html1_path = os.path.join(gt_html_dir, "render1.html")
        
        if (os.path.exists(render1_path) and os.path.exists(gt_render1_path) and
            os.path.exists(html1_path) and os.path.exists(gt_html1_path)):
            try:
                # Read HTML files
                with open(html1_path, 'r', encoding='utf-8') as f:
                    proposal_html = f.read()
                with open(gt_html1_path, 'r', encoding='utf-8') as f:
                    gt_html = f.read()
                
                # Compute all 5 metrics
                block_score = block_metric(proposal_html, gt_html)
                text_score = text_metric(proposal_html, gt_html)
                position_score = position_metric(proposal_html, gt_html)
                color_score = color_metric(proposal_html, gt_html)
                
                # CLIP metric (visual similarity)
                proposal_render = Image.open(render1_path)
                gt_render = Image.open(gt_render1_path)
                clip_score = float(clip_similarity(proposal_render, gt_render))
                
                # Store scores
                block_scores.append(block_score)
                text_scores.append(text_score)
                position_scores.append(position_score)
                color_scores.append(color_score)
                clip_scores.append(clip_score)
                
                task_instance_scores[round_dir]['render1'] = {
                    'block': block_score,
                    'text': text_score,
                    'position': position_score,
                    'color': color_score,
                    'clip': clip_score
                }
            except Exception as e:
                print(f"Error processing render1 for {task_dir}/{round_dir}: {e}")

        # Process render2
        render2_path = os.path.join(round_path, "render2.png")
        gt_render2_path = os.path.join(gt_renders_dir, "render2.png")
        html2_path = os.path.join(html_round_path, "render2.html")
        gt_html2_path = os.path.join(gt_html_dir, "render2.html")
        
        if (os.path.exists(render2_path) and os.path.exists(gt_render2_path) and
            os.path.exists(html2_path) and os.path.exists(gt_html2_path)):
            try:
                # Read HTML files
                with open(html2_path, 'r', encoding='utf-8') as f:
                    proposal_html2 = f.read()
                with open(gt_html2_path, 'r', encoding='utf-8') as f:
                    gt_html2 = f.read()
                
                # Compute all 5 metrics
                block_score2 = block_metric(proposal_html2, gt_html2)
                text_score2 = text_metric(proposal_html2, gt_html2)
                position_score2 = position_metric(proposal_html2, gt_html2)
                color_score2 = color_metric(proposal_html2, gt_html2)
                
                # CLIP metric (visual similarity)
                proposal_render2 = Image.open(render2_path)
                gt_render2 = Image.open(gt_render2_path)
                clip_score2 = float(clip_similarity(proposal_render2, gt_render2))
                
                # Store scores
                block_scores.append(block_score2)
                text_scores.append(text_score2)
                position_scores.append(position_score2)
                color_scores.append(color_score2)
                clip_scores.append(clip_score2)
                
                task_instance_scores[round_dir]['render2'] = {
                    'block': block_score2,
                    'text': text_score2,
                    'position': position_score2,
                    'color': color_score2,
                    'clip': clip_score2
                }
            except Exception as e:
                print(f"Error processing render2 for {task_dir}/{round_dir}: {e}")

        # Calculate average scores for this round
        if block_scores and text_scores and position_scores and color_scores and clip_scores:
            task_instance_scores[round_dir]['avg_block'] = sum(block_scores) / len(block_scores)
            task_instance_scores[round_dir]['avg_text'] = sum(text_scores) / len(text_scores)
            task_instance_scores[round_dir]['avg_position'] = sum(position_scores) / len(position_scores)
            task_instance_scores[round_dir]['avg_color'] = sum(color_scores) / len(color_scores)
            task_instance_scores[round_dir]['avg_clip'] = sum(clip_scores) / len(clip_scores)

    # Determine best rounds for each metric
    valid_rounds = {k: v for k, v in task_instance_scores.items() 
                   if all(key in v for key in ['avg_block', 'avg_text', 'avg_position', 'avg_color', 'avg_clip'])}
    
    best_scores = None
    if valid_rounds:
        best_scores = {
            'block': max(valid_rounds.values(), key=lambda x: x['avg_block'])['avg_block'],
            'text': max(valid_rounds.values(), key=lambda x: x['avg_text'])['avg_text'],
            'position': max(valid_rounds.values(), key=lambda x: x['avg_position'])['avg_position'],
            'color': max(valid_rounds.values(), key=lambda x: x['avg_color'])['avg_color'],
            'clip': max(valid_rounds.values(), key=lambda x: x['avg_clip'])['avg_clip']
        }

    # Save individual instance scores
    instance_scores_path = os.path.join(task_instance_dir, 'scores.json')
    try:
        with open(instance_scores_path, 'w') as f:
            json.dump(task_instance_scores, f, indent=4)
    except Exception:
        pass

    return task_dir, task_instance_scores, best_scores


def extract_task_type_and_number(task_dir_name):
    """
    Extract task type and number from directory name like 'design1', 'layout5', etc.
    
    Args:
        task_dir_name (str): Directory name like 'design1', 'layout5'
        
    Returns:
        tuple: (task_type, task_number) or (None, None) if invalid
    """
    # Common Design2Code task types
    task_types = ['design', 'layout', 'component', 'page', 'form', 'dashboard', 'landing']
    
    for task_type in task_types:
        if task_dir_name.startswith(task_type):
            try:
                task_number = int(task_dir_name[len(task_type):])
                return task_type, task_number
            except ValueError:
                continue
    return None, None


def main():
    parser = argparse.ArgumentParser(description='Evaluate AgenticVerifier Design2Code results')
    parser.add_argument('test_id', type=str, help='Test ID (e.g., 20250815_150016)')
    parser.add_argument('--output_dir', type=str, default=None, 
                       help='Output directory for evaluation results (default: output/design2code/{test_id}/_evaluation)')
    parser.add_argument('--missing_round_penalty_max', type=float, default=0.5,
                        help='Max penalty factor for earliest rounds (0-1, lower is more penalty).')
    parser.add_argument('--missing_round_penalty_min', type=float, default=0.9,
                        help='Min penalty factor for latest rounds (0-1, higher is less penalty).')
    
    args = parser.parse_args()
    test_id = args.test_id
    penalty_max = float(args.missing_round_penalty_max)
    penalty_min = float(args.missing_round_penalty_min)
    MAX_ROUNDS = 10
    
    # Set up paths
    output_base_dir = f"output/design2code/{test_id}"
    if not os.path.exists(output_base_dir):
        raise ValueError(f"Output directory {output_base_dir} does not exist.")
    
    if args.output_dir:
        eval_output_dir = args.output_dir
    else:
        eval_output_dir = os.path.join(output_base_dir, "_evaluation")
    
    os.makedirs(eval_output_dir, exist_ok=True)
    
    # Get all task directories
    task_dirs = [d for d in os.listdir(output_base_dir) 
                if os.path.isdir(os.path.join(output_base_dir, d)) and d != "evaluation"]
    
    print(f"Found {len(task_dirs)} task directories in {output_base_dir}")
    
    # Group tasks by type
    tasks_by_type = {}
    for task_dir in task_dirs:
        task_type, task_number = extract_task_type_and_number(task_dir)
        if task_type and task_number:
            if task_type not in tasks_by_type:
                tasks_by_type[task_type] = []
            tasks_by_type[task_type].append((task_dir, task_number))
    
    print(f"Grouped tasks by type: {list(tasks_by_type.keys())}")
    
    scores_across_tasks = {}
    intermediates = {}
    
    # Ensure CLIP is loaded once (shared by threads)
    ensure_clip_loaded()

    for task_type, task_instances in tasks_by_type.items():
        print(f"\nProcessing task type: {task_type}")

        # Sort by task number
        task_instances.sort(key=lambda x: x[1])

        scores_across_instances = {
            'best_block': [],
            'best_text': [],
            'best_position': [],
            'best_color': [],
            'best_clip': [],
            'instance_details': {}
        }

        # Run per-instance processing in parallel threads
        max_workers = min(8, (os.cpu_count() or 4))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(process_design2code_instance, output_base_dir, task_dir)
                for task_dir, _ in task_instances
            ]

            for future in tqdm(as_completed(futures), total=len(futures), desc=f"Processing {task_type}"):
                try:
                    task_dir, task_instance_scores, best_scores = future.result()
                    scores_across_instances['instance_details'][task_dir] = task_instance_scores
                    if best_scores is not None:
                        scores_across_instances['best_block'].append(best_scores['block'])
                        scores_across_instances['best_text'].append(best_scores['text'])
                        scores_across_instances['best_position'].append(best_scores['position'])
                        scores_across_instances['best_color'].append(best_scores['color'])
                        scores_across_instances['best_clip'].append(best_scores['clip'])
                        print(f"    {task_dir}: Block={best_scores['block']:.4f}, Text={best_scores['text']:.4f}, "
                              f"Position={best_scores['position']:.4f}, Color={best_scores['color']:.4f}, "
                              f"CLIP={best_scores['clip']:.4f}")
                    else:
                        print(f"    {task_dir}: No valid scores")
                except Exception as e:
                    print(f"    Error processing {task_type} instance: {e}")

        # Aggregate per-round averages across all instances (rounds 1..9)
        per_round_values = {str(i): {
            'block': [], 'text': [], 'position': [], 'color': [], 'clip': [], 'penalized_count': 0
        } for i in range(1, 11)}
        
        for instance_scores in scores_across_instances['instance_details'].values():
            # Collect available round indices for this instance
            available_rounds = sorted(
                [int(r) for r, v in instance_scores.items() if isinstance(v, dict) and 
                 all(key in v for key in ['avg_block', 'avg_text', 'avg_position', 'avg_color', 'avg_clip'])]
            )
            if not available_rounds:
                continue
            max_available_round = max(available_rounds)

            for round_idx in range(1, 11):
                key = str(round_idx)
                # Case 1: round exists normally
                if key in instance_scores and all(metric in instance_scores[key] for metric in ['avg_block', 'avg_text', 'avg_position', 'avg_color', 'avg_clip']):
                    per_round_values[key]['block'].append(instance_scores[key]['avg_block'])
                    per_round_values[key]['text'].append(instance_scores[key]['avg_text'])
                    per_round_values[key]['position'].append(instance_scores[key]['avg_position'])
                    per_round_values[key]['color'].append(instance_scores[key]['avg_color'])
                    per_round_values[key]['clip'].append(instance_scores[key]['avg_clip'])
                    continue

                # Case 2: earlier round missing but later rounds exist -> penalize
                if round_idx < max_available_round:
                    # Find the next available later round to base the penalty on
                    later_rounds = [r for r in available_rounds if r > round_idx]
                    if not later_rounds:
                        continue
                    next_round = min(later_rounds)
                    next_key = str(next_round)
                    base_scores = {
                        'block': instance_scores[next_key]['avg_block'],
                        'text': instance_scores[next_key]['avg_text'],
                        'position': instance_scores[next_key]['avg_position'],
                        'color': instance_scores[next_key]['avg_color'],
                        'clip': instance_scores[next_key]['avg_clip']
                    }
                    # Decaying penalty: higher for earlier rounds, lower for later rounds
                    if MAX_ROUNDS > 1:
                        t = (round_idx - 1) / (MAX_ROUNDS - 1)
                    else:
                        t = 0.0
                    penalty_factor_round = penalty_max + t * (penalty_min - penalty_max)
                    per_round_values[key]['block'].append(base_scores['block'] * penalty_factor_round)
                    per_round_values[key]['text'].append(base_scores['text'] * penalty_factor_round)
                    per_round_values[key]['position'].append(base_scores['position'] * penalty_factor_round)
                    per_round_values[key]['color'].append(base_scores['color'] * penalty_factor_round)
                    per_round_values[key]['clip'].append(base_scores['clip'] * penalty_factor_round)
                    per_round_values[key]['penalized_count'] += 1
                    continue
                # Case 3: missing because process ended (no later rounds) -> ignore

        per_round_summary = {}
        for key, vals in per_round_values.items():
            if vals['block'] and vals['text'] and vals['position'] and vals['color'] and vals['clip']:
                per_round_summary[key] = {
                    'avg_block': sum(vals['block']) / len(vals['block']),
                    'avg_text': sum(vals['text']) / len(vals['text']),
                    'avg_position': sum(vals['position']) / len(vals['position']),
                    'avg_color': sum(vals['color']) / len(vals['color']),
                    'avg_clip': sum(vals['clip']) / len(vals['clip']),
                    'num_instances': len(vals['block']),
                    'num_penalized': int(vals['penalized_count'])
                }

        # Store per-round aggregation in intermediates structure too
        scores_across_instances['per_round'] = per_round_summary

        # Aggregate results for this task type
        if scores_across_instances['best_block']:
            scores_across_tasks[task_type] = {
                'best_block': sum(scores_across_instances['best_block']) / len(scores_across_instances['best_block']),
                'best_text': sum(scores_across_instances['best_text']) / len(scores_across_instances['best_text']),
                'best_position': sum(scores_across_instances['best_position']) / len(scores_across_instances['best_position']),
                'best_color': sum(scores_across_instances['best_color']) / len(scores_across_instances['best_color']),
                'best_clip': sum(scores_across_instances['best_clip']) / len(scores_across_instances['best_clip']),
                'num_instances': len(scores_across_instances['best_block']),
                'per_round': per_round_summary
            }

            print(f"  Task {task_type} overall scores:")
            print(f"    Average best Block: {scores_across_tasks[task_type]['best_block']:.4f}")
            print(f"    Average best Text: {scores_across_tasks[task_type]['best_text']:.4f}")
            print(f"    Average best Position: {scores_across_tasks[task_type]['best_position']:.4f}")
            print(f"    Average best Color: {scores_across_tasks[task_type]['best_color']:.4f}")
            print(f"    Average best CLIP: {scores_across_tasks[task_type]['best_clip']:.4f}")
            print(f"    Number of instances: {scores_across_tasks[task_type]['num_instances']}")
        else:
            print(f"  No valid scores for task type {task_type}")
            scores_across_tasks[task_type] = {}

        intermediates[task_type] = scores_across_instances
    
    # Save overall results
    overall_scores_path = os.path.join(eval_output_dir, 'overall_scores.json')
    with open(overall_scores_path, 'w') as f:
        json.dump(scores_across_tasks, f, indent=4)
    
    intermediate_scores_path = os.path.join(eval_output_dir, 'intermediate_scores.json')
    with open(intermediate_scores_path, 'w') as f:
        json.dump(intermediates, f, indent=4)
    
    # Print summary
    print(f"\n=== Design2Code Evaluation Summary ===")
    print(f"Test ID: {test_id}")
    print(f"Output directory: {eval_output_dir}")
    print(f"Results saved to: {overall_scores_path}")
    
    for task_type, scores in scores_across_tasks.items():
        if scores:
            print(f"\n{task_type.upper()}:")
            print(f"  Average best Block: {scores['best_block']:.4f}")
            print(f"  Average best Text: {scores['best_text']:.4f}")
            print(f"  Average best Position: {scores['best_position']:.4f}")
            print(f"  Average best Color: {scores['best_color']:.4f}")
            print(f"  Average best CLIP: {scores['best_clip']:.4f}")
            print(f"  Instances evaluated: {scores['num_instances']}")
        else:
            print(f"\n{task_type.upper()}: No valid scores")


if __name__ == "__main__":
    main()
