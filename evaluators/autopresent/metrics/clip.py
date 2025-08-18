"""CLIP image-pair similarity score."""

import cv2
import clip
import torch
import argparse
import numpy as np
from PIL import Image, ImageDraw

device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)


# %% Score Implementation

def mask_bounding_boxes_with_inpainting(image, bounding_boxes):
    # Convert PIL image to OpenCV format
    image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    # Create a black mask
    mask = np.zeros(image_cv.shape[:2], dtype=np.uint8)

    height, width = image_cv.shape[:2]

    # Draw white rectangles on the mask
    for bbox in bounding_boxes:
        x_ratio, y_ratio, w_ratio, h_ratio = bbox
        x = int(x_ratio * width)
        y = int(y_ratio * height)
        w = int(w_ratio * width)
        h = int(h_ratio * height)
        mask[y:y+h, x:x+w] = 255

    # Use inpainting
    inpainted_image = cv2.inpaint(image_cv, mask, 3, cv2.INPAINT_TELEA)

    # Convert back to PIL format
    inpainted_image_pil = Image.fromarray(cv2.cvtColor(inpainted_image, cv2.COLOR_BGR2RGB))

    return inpainted_image_pil

def rescale_and_mask(image_path, blocks):
    # Load the image
    with Image.open(image_path) as img:
        if len(blocks) > 0:
            # use inpainting instead of simple mask
            img = mask_bounding_boxes_with_inpainting(img, blocks)

        width, height = img.size

        # Determine which side is shorter
        if width < height:
            # Width is shorter, scale height to match the width
            new_size = (width, width)
        else:
            # Height is shorter, scale width to match the height
            new_size = (height, height)

        # Resize the image while maintaining aspect ratio
        img_resized = img.resize(new_size, Image.LANCZOS)

        return img_resized


def get_clip_similarity(image_path1, image_path2, blocks1, blocks2):
    # Load and preprocess images
    image1 = preprocess(rescale_and_mask(image_path1, [block['bbox'] for block in blocks1])).unsqueeze(0).to(device)
    image2 = preprocess(rescale_and_mask(image_path2, [block['bbox'] for block in blocks2])).unsqueeze(0).to(device)

    # Calculate features
    with torch.no_grad():
        image_features1 = model.encode_image(image1)
        image_features2 = model.encode_image(image2)

    # Normalize features
    image_features1 /= image_features1.norm(dim=-1, keepdim=True)
    image_features2 /= image_features2.norm(dim=-1, keepdim=True)

    # Calculate cosine similarity
    similarity = (image_features1 @ image_features2.T).item()

    return similarity


# %% Test the function
def test():
    clip_sim = get_clip_similarity(args.image_path_1, args.image_path_2, [], [])
    print("CLIP similarity score:", clip_sim)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLIP image-pair similarity score.")
    parser.add_argument("--image_path_1", type=str, help="Path to the first image.")
    parser.add_argument("--image_path_2", type=str, help="Path to the second image.")
    args = parser.parse_args()
    
    test()
