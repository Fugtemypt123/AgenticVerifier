"""Text similarity metric by calculating character overlaps."""

from difflib import SequenceMatcher
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

def get_text_similarity_prev(text1: str, text2: str) -> float:
    if (text1 is None) or (text2 is None): return None
    return SequenceMatcher(None, text1, text2).ratio()

# Load a pretrained sentence-transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')  # You can use other models from SentenceTransformers

def get_text_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return None  # Handle None or empty input gracefully

    # Generate embeddings for the input texts
    embeddings = model.encode([text1, text2], convert_to_tensor=True).cpu()

    # Compute cosine similarity between the two embeddings
    similarity = cosine_similarity(embeddings[0].reshape(1, -1), embeddings[1].reshape(1, -1))

    return similarity[0][0]  # Return the scalar similarity score

# test
text1 = "Language for Robots Circa 2018"
text2 = "Language for Robots Circa 2020"
get_text_similarity(text1, text2)
