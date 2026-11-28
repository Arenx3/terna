"""The local embedding model: a multilingual sentence encoder, on the CPU.

Spanish and English land in the same space, so a requirement written in one
finds its evidence in a résumé written in the other. The model is downloaded
once from Hugging Face into the ml worker's `/models` volume; after that it is
read from disk only, and no screening reaches the network.

Only the ml worker imports the model (`uv` group `embeddings`). Everything
else reads the vectors it stored, through pgvector.
"""

import logging
from functools import cache

from django.conf import settings
from django.db import connection

from screening.models import RequirementVector, ResumePassage

logger = logging.getLogger(__name__)


def name() -> str:
    """Stored next to every vector: vectors from two models aren't comparable."""
    return settings.EMBEDDING_MODEL


@cache
def _model():
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(settings.ML_THREADS)
    options = {"device": "cpu", "revision": settings.EMBEDDING_MODEL_REVISION}
    try:
        return SentenceTransformer(settings.EMBEDDING_MODEL, local_files_only=True, **options)
    except Exception:  # not on disk yet: the only time it reaches the network
        logger.info("Downloading %s, once, into the model cache", settings.EMBEDDING_MODEL)
        return SentenceTransformer(settings.EMBEDDING_MODEL, **options)


def load() -> None:
    """Have the model ready (downloading it if needed) before the first screening."""
    _model()


def encode(texts: list[str]) -> list[list[float]]:
    """Unit-length vectors, so cosine similarity is a dot product."""
    if not texts:
        return []
    vectors = _model().encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return [vector.tolist() for vector in vectors]


def similarities(resume_id, requirement_ids: list[int]) -> dict[int, dict[int, float]]:
    """{requirement id: {passage id: cosine similarity}}, computed by pgvector.

    Exact distances over one résumé's passages (a few dozen), not the HNSW index:
    an approximate scan filtered down to one résumé can come back short.
    """
    if not requirement_ids:
        return {}
    passages = ResumePassage._meta.db_table
    vectors = RequirementVector._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT v.requirement_id, p.id, 1 - (p.embedding <=> v.embedding) "  # noqa: S608 (table names)
            f"FROM {passages} p JOIN {vectors} v ON v.requirement_id = ANY(%s) "
            f"WHERE p.resume_id = %s AND p.embedding IS NOT NULL AND v.model = %s",
            [requirement_ids, resume_id, name()],
        )
        out: dict[int, dict[int, float]] = {}
        for requirement_id, passage_id, similarity in cursor.fetchall():
            out.setdefault(requirement_id, {})[passage_id] = float(similarity)
        return out
