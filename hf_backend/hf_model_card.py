from __future__ import annotations
import logging
from typing import Optional

from hf_backend.hf_auth import get_api
from hf_backend.hf_files import get_file_content, upload_file_content, HFFileError

logger = logging.getLogger(__name__)


class HFModelCardError(RuntimeError):
    pass


_YAML_SPECIAL = set(':{}[],"\'|>&*!#%@`\n\r')
_YAML_BOOLS = {'true', 'false', 'yes', 'no', 'null', 'on', 'off'}


def _yaml_quote(value: str) -> str:
    if not value:
        return '""'
    if (any(ch in _YAML_SPECIAL for ch in value)
            or value.strip() != value
            or value.lower() in _YAML_BOOLS):
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        escaped = escaped.replace('\n', '\\n').replace('\r', '\\r')
        return f'"{escaped}"'
    return value


PIPELINE_TAGS = [
    "",
    "text-generation",
    "text2text-generation",
    "text-classification",
    "token-classification",
    "question-answering",
    "translation",
    "summarization",
    "fill-mask",
    "conversational",
    "image-classification",
    "image-segmentation",
    "object-detection",
    "image-to-text",
    "text-to-image",
    "text-to-speech",
    "automatic-speech-recognition",
    "audio-classification",
    "feature-extraction",
    "sentence-similarity",
    "zero-shot-classification",
    "reinforcement-learning",
    "tabular-classification",
    "tabular-regression",
    "depth-estimation",
    "video-classification",
]

LICENSES = [
    "",
    "apache-2.0",
    "mit",
    "gpl-3.0",
    "gpl-2.0",
    "bsd-3-clause",
    "bsd-2-clause",
    "cc-by-4.0",
    "cc-by-sa-4.0",
    "cc-by-nc-4.0",
    "cc-by-nc-sa-4.0",
    "cc0-1.0",
    "openrail",
    "openrail++",
    "llama3",
    "llama3.1",
    "llama3.2",
    "gemma",
    "bigscience-bloom-rail-1.0",
    "bigscience-openrail-m",
    "creativeml-openrail-m",
    "unlicense",
    "other",
]

LIBRARY_NAMES = [
    "",
    "transformers",
    "diffusers",
    "sentence-transformers",
    "adapter-transformers",
    "timm",
    "spacy",
    "flair",
    "fairseq",
    "allennlp",
    "stanza",
    "espnet",
    "speechbrain",
    "paddlenlp",
    "peft",
    "fastai",
    "stable-baselines3",
    "ml-agents",
    "keras",
    "tensorflow",
    "pytorch",
    "jax",
    "onnx",
    "safetensors",
    "ctranslate2",
    "gguf",
    "mlx",
    "other",
]

COMMON_LANGUAGES = [
    "",
    "en",
    "zh",
    "es",
    "fr",
    "de",
    "ja",
    "ko",
    "pt",
    "ru",
    "ar",
    "hi",
    "it",
    "nl",
    "pl",
    "tr",
    "multilingual",
]


def generate_model_card_yaml(
    language: str = "",
    license: str = "",
    library_name: str = "",
    pipeline_tag: str = "",
    tags: list[str] | None = None,
    base_model: str = "",
    datasets: list[str] | None = None,
    extra_metadata: dict | None = None,
) -> str:
    """Generate the YAML frontmatter for a model card."""
    lines = ["---"]

    if language:
        lines.append(f"language: {_yaml_quote(language)}")
    if license:
        lines.append(f"license: {_yaml_quote(license)}")
    if library_name:
        lines.append(f"library_name: {_yaml_quote(library_name)}")
    if pipeline_tag:
        lines.append(f"pipeline_tag: {_yaml_quote(pipeline_tag)}")
    if base_model:
        lines.append(f"base_model: {_yaml_quote(base_model)}")

    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {_yaml_quote(t)}")

    if datasets:
        lines.append("datasets:")
        for d in datasets:
            lines.append(f"  - {_yaml_quote(d)}")

    if extra_metadata:
        for k, v in extra_metadata.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {_yaml_quote(str(item))}")
            else:
                lines.append(f"{k}: {_yaml_quote(str(v))}")

    lines.append("---")
    return "\n".join(lines)


def generate_model_card(
    model_name: str = "My Model",
    language: str = "",
    license: str = "",
    library_name: str = "",
    pipeline_tag: str = "",
    tags: list[str] | None = None,
    base_model: str = "",
    datasets: list[str] | None = None,
    model_description: str = "",
    intended_use: str = "",
    training_details: str = "",
    evaluation: str = "",
    limitations: str = "",
    extra_metadata: dict | None = None,
) -> str:
    """Generate a full model card (YAML + Markdown body)."""
    yaml = generate_model_card_yaml(
        language=language,
        license=license,
        library_name=library_name,
        pipeline_tag=pipeline_tag,
        tags=tags,
        base_model=base_model,
        datasets=datasets,
        extra_metadata=extra_metadata,
    )

    sections = [yaml, ""]
    sections.append(f"# {model_name}")
    sections.append("")

    if model_description:
        sections.append("## Model Description")
        sections.append("")
        sections.append(model_description)
        sections.append("")

    if intended_use:
        sections.append("## Intended Use")
        sections.append("")
        sections.append(intended_use)
        sections.append("")

    if training_details:
        sections.append("## Training Details")
        sections.append("")
        sections.append(training_details)
        sections.append("")

    if evaluation:
        sections.append("## Evaluation")
        sections.append("")
        sections.append(evaluation)
        sections.append("")

    if limitations:
        sections.append("## Limitations and Biases")
        sections.append("")
        sections.append(limitations)
        sections.append("")

    return "\n".join(sections)


def get_readme(repo_id: str, repo_type: str = "model") -> str:
    """Fetch the current README.md from a repo."""
    try:
        return get_file_content(repo_id, "README.md", repo_type=repo_type)
    except HFFileError as e:
        logger.debug("No README found for %s: %s", repo_id, e)
        return ""


def push_readme(
    repo_id: str,
    content: str,
    repo_type: str = "model",
    commit_message: str = "Update README.md",
) -> str:
    """Push a README.md to a repo."""
    try:
        return upload_file_content(
            repo_id=repo_id,
            content=content,
            path_in_repo="README.md",
            repo_type=repo_type,
            commit_message=commit_message,
        )
    except HFFileError as e:
        logger.error("Failed to push README to %s: %s", repo_id, e)
        raise HFModelCardError(f"Failed to push README: {e}") from e
