import logging
import logging
from typing import Dict, Any, Optional
from sklearn.feature_extraction.text import HashingVectorizer

logger = logging.getLogger(__name__)

class SparseEmbeddingService:
    """
    Service to generate sparse embeddings locally for Hybrid Search.
    Uses HashingVectorizer for stateless, scalable, consistent token-to-dimension mapping
    across distributed workers without requiring shared model state.
    """
    _instance = None
    # Dimension size for the sparse vector. 
    # 30,000 is a reasonable balance for vocabulary size vs sparsity for this use case.
    # Vertex AI supports large sparse dimensions.
    N_FEATURES = 30000 
    
    _vectorizer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SparseEmbeddingService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # HashingVectorizer is stateless. It maps tokens to indices using a hash function.
        # alternate_sign=False ensures values are non-negative (compatible with some index types)
        # norm='l2' ensures vectors are normalized.
        self._vectorizer = HashingVectorizer(
            n_features=self.N_FEATURES,
            analyzer='word',
            stop_words='english',
            alternate_sign=False, 
            norm='l2'
        )

    async def initialize_and_fit(self):
        """
        No-op for HashingVectorizer as it is stateless.
        Kept for compatibility or future interface checks.
        """
        pass

    def get_sparse_embedding(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Generates sparse embedding for a given text.
        Returns format: {'values': [float], 'dimensions': [int]}
        """
        if not text:
            return None
            
        try:
            # Transform returns a sparse matrix (csr_matrix)
            matrix = self._vectorizer.transform([text])
            coo = matrix.tocoo()
            
            # Sort by dimension index to ensure canonical order (good practice)
            # COOC format might not be sorted. zip->sort->unzip
            data_dim_pairs = sorted(zip(coo.col, coo.data))
            
            dimensions = [int(p[0]) for p in data_dim_pairs]
            values = [float(p[1]) for p in data_dim_pairs]
            
            return {
                "values": values,
                "dimensions": dimensions
            }
        except Exception as e:
            logger.error(f"Failed to generate sparse embedding: {e}")
            return None
