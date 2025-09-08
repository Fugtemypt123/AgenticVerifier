# Design2Code Evaluation Script

This script evaluates AgenticVerifier results for Design2Code tasks, comparing generated HTML/CSS code and rendered images against ground truth.

## Features

- **Block Metric**: Compares block-level elements structure (div, section, article, etc.)
- **Text Metric**: Analyzes text content and styling (font-size, font-family, etc.)
- **Position Metric**: Evaluates element positioning (position, margin, padding, etc.)
- **Color Metric**: Compares color properties using RGB distance
- **CLIP Metric**: Uses CLIP model to compare visual similarity of rendered images
- **Multi-round Evaluation**: Supports evaluation across multiple generation rounds
- **Parallel Processing**: Efficient processing of multiple task instances
- **Penalty System**: Handles missing rounds with configurable penalties

## Installation

1. Install core dependencies:
```bash
pip install torch torchvision transformers Pillow numpy tqdm
```

2. Install optional dependencies for enhanced functionality:
```bash
pip install beautifulsoup4 playwright selenium
```

3. Install browser for playwright (if using playwright):
```bash
playwright install chromium
```

## Usage

### Basic Usage
```bash
python evaluate.py <test_id>
```

### Advanced Usage
```bash
python evaluate.py <test_id> \
    --output_dir /path/to/evaluation/results \
    --missing_round_penalty_max 0.5 \
    --missing_round_penalty_min 0.9
```

### Parameters

- `test_id`: Test ID (e.g., 20250815_150016)
- `--output_dir`: Output directory for evaluation results (default: output/design2code/{test_id}/_evaluation)
- `--missing_round_penalty_max`: Max penalty factor for earliest rounds (0-1, lower is more penalty)
- `--missing_round_penalty_min`: Min penalty factor for latest rounds (0-1, higher is less penalty)

## Directory Structure

The script expects the following directory structure:

```
output/design2code/{test_id}/
├── design1/
│   ├── renders/
│   │   ├── 1/
│   │   │   ├── render1.png
│   │   │   └── render2.png
│   │   └── 2/
│   │       ├── render1.png
│   │       └── render2.png
│   └── html/
│       ├── 1/
│       │   ├── render1.html
│       │   └── render2.html
│       └── 2/
│           ├── render1.html
│           └── render2.html
└── design2/
    └── ...
```

Ground truth files should be located at:
```
data/design2code/{task_dir}/
├── renders/goal/
│   ├── render1.png
│   └── render2.png
└── html/goal/
    ├── render1.html
    └── render2.html
```

## Metrics

The evaluation script implements the 5 core metrics from Design2Code:

### Block Metric
- Compares block-level elements structure (div, section, article, header, footer, main, aside, nav)
- Analyzes element count and type distribution
- Range: 0-1 (higher is more similar)

### Text Metric
- Compares text content and styling properties
- Analyzes font-size, font-family, font-weight, color
- Range: 0-1 (higher is more similar)

### Position Metric
- Evaluates element positioning properties
- Analyzes position, top, left, right, bottom, margin, padding, width, height
- Range: 0-1 (higher is more similar)

### Color Metric
- Compares color properties using RGB distance
- Supports hex, rgb(), rgba(), and named colors
- Range: 0-1 (higher is more similar)

### CLIP Metric
- Uses CLIP (Contrastive Language-Image Pre-training) to compute visual similarity between rendered images
- Range: 0-1 (higher is more similar)

## Output

The script generates:

1. **overall_scores.json**: Aggregated scores across all task types
2. **intermediate_scores.json**: Detailed scores for each task instance and round
3. **Individual scores.json**: Per-instance scores in each task directory

### Example Output Structure

```json
{
  "design": {
    "best_block": 0.85,
    "best_text": 0.78,
    "best_position": 0.72,
    "best_color": 0.80,
    "best_clip": 0.75,
    "num_instances": 10,
    "per_round": {
      "1": {
        "avg_block": 0.75,
        "avg_text": 0.70,
        "avg_position": 0.68,
        "avg_color": 0.72,
        "avg_clip": 0.69,
        "num_instances": 10,
        "num_penalized": 0
      }
    }
  }
}
```

## Task Types

The script automatically detects task types from directory names:
- `design*`: Design tasks
- `layout*`: Layout tasks  
- `component*`: Component tasks
- `page*`: Page tasks
- `form*`: Form tasks
- `dashboard*`: Dashboard tasks
- `landing*`: Landing page tasks

## Dependencies

### Required
- Python 3.7+
- PyTorch
- Transformers (Hugging Face)
- PIL/Pillow
- NumPy
- tqdm

### Optional (for enhanced functionality)
- BeautifulSoup4: HTML parsing and structure analysis
- Playwright: HTML rendering (recommended)
- Selenium: HTML rendering (fallback)
- wkhtmltoimage: HTML rendering (last resort)

## Notes

- The script uses parallel processing for efficiency
- Missing rounds are handled with configurable penalty factors
- HTML rendering is optional and falls back gracefully if not available
- All similarity scores are normalized to [0, 1] range
