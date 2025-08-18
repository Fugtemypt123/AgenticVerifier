"""Calculate color similarity of two matched blocks."""

import numpy
def patch_asscalar(a):
    return a.item()
setattr(numpy, "asscalar", patch_asscalar)


import argparse
import numpy as np
from PIL import Image
from colormath.color_objects import sRGBColor, LabColor
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000


def rgb_to_lab(rgb):
    """
    Convert an RGB color to Lab color space.
    RGB values should be in the range [0, 255].
    """
    # Create an sRGBColor object from RGB values
    rgb_color = sRGBColor(rgb[0], rgb[1], rgb[2], is_upscaled=True)
    
    # Convert to Lab color space
    lab_color = convert_color(rgb_color, LabColor)
    
    return lab_color


def color_similarity_ciede2000(rgb1, rgb2):
    """
    Calculate the color similarity between two RGB colors using the CIEDE2000 formula.
    Returns a similarity score between 0 and 1, where 1 means identical.
    """
    # Convert RGB colors to Lab
    lab1 = rgb_to_lab(rgb1)
    lab2 = rgb_to_lab(rgb2)
    
    # Calculate the Delta E (CIEDE2000)
    delta_e = delta_e_cie2000(lab1, lab2)
    
    # Normalize the Delta E value to get a similarity score
    # Note: The normalization method here is arbitrary and can be adjusted based on your needs.
    # A delta_e of 0 means identical colors. Higher values indicate more difference.
    # For visualization purposes, we consider a delta_e of 100 to be completely different.
    similarity = max(0, 1 - (delta_e / 100))
    
    return similarity


def get_color_similarity(color1: tuple, color2: tuple) -> float:
    if (color1 is None) and (color2 is None): return 1.0
    elif (color1 is None) or (color2 is None): return 0.0
    return color_similarity_ciede2000(color1, color2)


# %% Get shape fill similarity
import pptx
from pptx.enum.dml import MSO_FILL_TYPE
from pptx.enum.dml import MSO_COLOR_TYPE

def get_shape_fill_similarity(shape1: str | pptx.dml.fill.FillFormat, shape2: str | pptx.dml.fill.FillFormat):
    # if image fill, compare if image blob is the same
    if isinstance(shape1, bytes) or isinstance(shape2, bytes):
        return int(shape1 == shape2)
    
    # if color fill, compare the color similarity
    if shape1.type == shape2.type == MSO_FILL_TYPE.SOLID:
        if shape1.fore_color.type == shape2.fore_color.type == MSO_COLOR_TYPE.RGB:
            color1 = shape1.fore_color.rgb
            color2 = shape2.fore_color.rgb
            sim = get_color_similarity(color1, color2)
            return sim
        elif shape1.fore_color.type == shape2.fore_color.type == MSO_COLOR_TYPE.SCHEME:
            return int(shape1.fore_color.theme_color == shape2.fore_color.theme_color)
        else:
            return int(shape1 == shape2)
    elif shape1.type == shape2.type == MSO_FILL_TYPE.BACKGROUND:
        return 1.0
    else:
        return 0.0


# %% Test the function
def test():
    def average_color(image_path, coordinates):
        """
        Calculates the average color of the specified coordinates in the given image.

        :param image: A PIL Image object.
        :param coordinates: A 2D numpy array of coordinates, where each row represents [x, y].
        :return: A tuple representing the average color (R, G, B).
        """
        # Convert image to numpy array
        image_array = np.array(Image.open(image_path).convert('RGB'))

        # Extract colors at the specified coordinates
        colors = [image_array[x, y] for x, y in coordinates]

        # Calculate the average color
        avg_color = np.mean(colors, axis=0)

        return tuple(avg_color.astype(int))

    image_path_1 = "slides-bench/test/page1/page1.jpg"
    image_path_2 = "slides-bench/test/page1/gpt-4o-mini.png"
    color1 = average_color(image_path_1, [(0, 2)])
    color2 = average_color(image_path_2, [(1, 2)])
    color_sim = get_color_similarity(color1, color2)
    print("Color similarity score:", color_sim)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLIP image-pair similarity score.")
    parser.add_argument("--image_path_1", type=str, help="Path to the first image.")
    parser.add_argument("--image_path_2", type=str, help="Path to the second image.")
    args = parser.parse_args()
    
    test()
