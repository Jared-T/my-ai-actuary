"""
Embedding service for generating and managing vector embeddings.

Provides OpenAI embedding generation for knowledge base content,
enabling semantic search capabilities across actuarial methods,
templates, and precedents.
"""

import json
from datetime import datetime, timezone
from typing import Any

import tiktoken
from openai import AsyncOpenAI

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

# Default embedding model settings
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMENSIONS = 1536
MAX_TOKENS_PER_CHUNK = 8000  # Leave buffer for text-embedding-3-small's 8191 limit


class EmbeddingService:
    """
    Service for generating and managing text embeddings.

    Uses OpenAI's text-embedding models to create vector representations
    of text content for semantic search capabilities.
    """

    def __init__(
        self,
        model: str = DEFAULT_EMBEDDING_MODEL,
        dimensions: int | None = None,
    ):
        """
        Initialize the embedding service.

        Args:
            model: OpenAI embedding model to use
            dimensions: Optional output dimensions (for models that support it)
        """
        self.model = model
        self.dimensions = dimensions
        self._client: AsyncOpenAI | None = None
        self._tokenizer: tiktoken.Encoding | None = None

    @property
    def client(self) -> AsyncOpenAI:
        """Lazy-initialize OpenAI client."""
        if self._client is None:
            api_key = settings.openai_api_key.get_secret_value()
            if not api_key:
                raise ValueError("OpenAI API key not configured")
            self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    @property
    def tokenizer(self) -> tiktoken.Encoding:
        """Lazy-initialize tokenizer for the model."""
        if self._tokenizer is None:
            # Use cl100k_base encoding for embedding models (used by text-embedding-3-*)
            self._tokenizer = tiktoken.get_encoding("cl100k_base")
        return self._tokenizer

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text string.

        Args:
            text: Input text

        Returns:
            Number of tokens
        """
        return len(self.tokenizer.encode(text))

    def truncate_text(self, text: str, max_tokens: int = MAX_TOKENS_PER_CHUNK) -> str:
        """
        Truncate text to fit within token limit.

        Args:
            text: Input text
            max_tokens: Maximum number of tokens

        Returns:
            Truncated text
        """
        tokens = self.tokenizer.encode(text)
        if len(tokens) <= max_tokens:
            return text

        truncated_tokens = tokens[:max_tokens]
        return self.tokenizer.decode(truncated_tokens)

    async def generate_embedding(
        self,
        text: str,
        truncate: bool = True,
    ) -> list[float]:
        """
        Generate embedding vector for a single text input.

        Args:
            text: Text to embed
            truncate: Whether to truncate text if too long

        Returns:
            Embedding vector as list of floats

        Raises:
            ValueError: If text is empty or too long without truncation
        """
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text")

        # Truncate if needed
        if truncate:
            text = self.truncate_text(text)
        elif self.count_tokens(text) > MAX_TOKENS_PER_CHUNK:
            raise ValueError(
                f"Text exceeds maximum token limit of {MAX_TOKENS_PER_CHUNK}"
            )

        try:
            params: dict[str, Any] = {
                "input": text,
                "model": self.model,
            }

            # Add dimensions parameter if specified and supported
            if self.dimensions and "text-embedding-3" in self.model:
                params["dimensions"] = self.dimensions

            response = await self.client.embeddings.create(**params)
            embedding = response.data[0].embedding

            logger.debug(
                "Generated embedding",
                model=self.model,
                text_length=len(text),
                embedding_dimensions=len(embedding),
            )

            return embedding

        except Exception as e:
            logger.error(
                "Failed to generate embedding",
                error=str(e),
                model=self.model,
                text_length=len(text),
            )
            raise

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        truncate: bool = True,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in a batch.

        Args:
            texts: List of texts to embed
            truncate: Whether to truncate texts if too long

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Prepare texts
        processed_texts = []
        for text in texts:
            if not text or not text.strip():
                processed_texts.append("")
                continue

            if truncate:
                processed_texts.append(self.truncate_text(text))
            else:
                processed_texts.append(text)

        # Filter out empty texts and track indices
        non_empty_texts = []
        non_empty_indices = []
        for i, text in enumerate(processed_texts):
            if text.strip():
                non_empty_texts.append(text)
                non_empty_indices.append(i)

        if not non_empty_texts:
            return [[] for _ in texts]

        try:
            params: dict[str, Any] = {
                "input": non_empty_texts,
                "model": self.model,
            }

            if self.dimensions and "text-embedding-3" in self.model:
                params["dimensions"] = self.dimensions

            response = await self.client.embeddings.create(**params)

            # Build result list with empty vectors for empty texts
            results: list[list[float]] = [[] for _ in texts]
            for i, embedding_data in enumerate(response.data):
                original_index = non_empty_indices[i]
                results[original_index] = embedding_data.embedding

            logger.debug(
                "Generated batch embeddings",
                model=self.model,
                batch_size=len(texts),
                non_empty_count=len(non_empty_texts),
            )

            return results

        except Exception as e:
            logger.error(
                "Failed to generate batch embeddings",
                error=str(e),
                model=self.model,
                batch_size=len(texts),
            )
            raise

    def embedding_to_json(self, embedding: list[float]) -> str:
        """
        Convert embedding vector to JSON string for storage.

        Args:
            embedding: Embedding vector

        Returns:
            JSON string representation
        """
        return json.dumps(embedding)

    def json_to_embedding(self, json_str: str) -> list[float]:
        """
        Convert JSON string back to embedding vector.

        Args:
            json_str: JSON string representation

        Returns:
            Embedding vector
        """
        return json.loads(json_str)

    def cosine_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score (-1 to 1)
        """
        if not embedding1 or not embedding2:
            return 0.0

        if len(embedding1) != len(embedding2):
            raise ValueError("Embeddings must have the same dimensions")

        # Calculate dot product and magnitudes
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        magnitude1 = sum(a * a for a in embedding1) ** 0.5
        magnitude2 = sum(b * b for b in embedding2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def prepare_method_text(
        self,
        name: str,
        summary: str,
        description: str,
        use_cases: str | None = None,
        implementation_guidance: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        Prepare actuarial method content for embedding.

        Combines relevant fields into a single text optimized for semantic search.

        Args:
            name: Method name
            summary: Brief summary
            description: Detailed description
            use_cases: Use cases (optional)
            implementation_guidance: Implementation guidance (optional)
            tags: Tags (optional)

        Returns:
            Combined text for embedding
        """
        parts = [
            f"Method: {name}",
            f"Summary: {summary}",
            f"Description: {description}",
        ]

        if use_cases:
            parts.append(f"Use Cases: {use_cases}")

        if implementation_guidance:
            parts.append(f"Implementation: {implementation_guidance}")

        if tags:
            parts.append(f"Tags: {', '.join(tags)}")

        return "\n\n".join(parts)

    def prepare_template_text(
        self,
        name: str,
        summary: str,
        description: str,
        output_format: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        Prepare template content for embedding.

        Args:
            name: Template name
            summary: Brief summary
            description: Detailed description
            output_format: Output format (optional)
            tags: Tags (optional)

        Returns:
            Combined text for embedding
        """
        parts = [
            f"Template: {name}",
            f"Summary: {summary}",
            f"Description: {description}",
        ]

        if output_format:
            parts.append(f"Format: {output_format}")

        if tags:
            parts.append(f"Tags: {', '.join(tags)}")

        return "\n\n".join(parts)

    def prepare_precedent_text(
        self,
        title: str,
        summary: str,
        description: str,
        context: str | None = None,
        industry: str | None = None,
        methods_used: list[str] | None = None,
        outcome: str | None = None,
        lessons_learned: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        Prepare precedent content for embedding.

        Args:
            title: Precedent title
            summary: Brief summary
            description: Detailed description
            context: Business context (optional)
            industry: Industry sector (optional)
            methods_used: Methods used (optional)
            outcome: Outcomes (optional)
            lessons_learned: Lessons learned (optional)
            tags: Tags (optional)

        Returns:
            Combined text for embedding
        """
        parts = [
            f"Case: {title}",
            f"Summary: {summary}",
            f"Description: {description}",
        ]

        if context:
            parts.append(f"Context: {context}")

        if industry:
            parts.append(f"Industry: {industry}")

        if methods_used:
            parts.append(f"Methods Used: {', '.join(methods_used)}")

        if outcome:
            parts.append(f"Outcome: {outcome}")

        if lessons_learned:
            parts.append(f"Lessons Learned: {lessons_learned}")

        if tags:
            parts.append(f"Tags: {', '.join(tags)}")

        return "\n\n".join(parts)


# Create a default instance for convenience
_default_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """
    Get the default embedding service instance.

    Returns:
        Default EmbeddingService instance
    """
    global _default_service
    if _default_service is None:
        _default_service = EmbeddingService()
    return _default_service
