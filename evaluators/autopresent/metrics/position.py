"""Calculate position similarity of two matched blocks."""

def calculate_distance_max_1d(x1, y1, x2, y2):
    distance = max(abs(x2 - x1), abs(y2 - y1))
    return distance

def get_x(block: dict) -> float:
    """Coordinates of the block (left, top, right, bottom)."""
    return (block['bbox'][0] + block['bbox'][2]) / 2

def get_y(block: dict) -> float:
    """Coordinates of the block (left, top, right, bottom)."""
    return (block['bbox'][1] + block['bbox'][3]) / 2

def get_position_similarity(block1: dict, block2: dict) -> float:
    position_similarity = 1 - calculate_distance_max_1d(
        get_x(block1), get_y(block1), get_x(block2), get_y(block2)
    )
    return max(0.0, position_similarity)

# test: all coordinates normalized to [0, 1] scale
block1 = {"bbox": [0, 0.1, 0.3, 0.8]}
block2 = {"bbox": [0, 0.5, 0.2, 0.6]}
get_position_similarity(block1, block2)