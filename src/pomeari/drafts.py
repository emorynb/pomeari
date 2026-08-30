import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

import frontmatter

from .errors import DraftError, DraftNotFoundError, InvalidDraftNameError
from .types import Draft, DraftSummary, PostForm


class DraftStore:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self):
        self.path.mkdir(parents=True, exist_ok=True)

    def _draft_path(self, name: str) -> Path:
        normalized = name.strip().removesuffix(".md")
        if not normalized:
            raise InvalidDraftNameError("Draft names cannot be empty.")
        if Path(normalized).name != normalized:
            raise InvalidDraftNameError("Draft names cannot contain a path.")

        return self.path / f"{normalized}.md"

    def save(self, draft: Draft):
        path = self._draft_path(draft.name)
        document = frontmatter.loads(draft.content)
        document.metadata["pomeari"] = {
            "post_form": draft.post_form.value,
            "targets": list(draft.targets),
        }

        temporary_path = path.with_suffix(".md.tmp")
        temporary_path.write_text(frontmatter.dumps(document), encoding="utf-8")
        temporary_path.replace(path)

    def load(self, name: str) -> Draft:
        path = self._draft_path(name)
        if not path.exists():
            raise DraftNotFoundError(name)

        try:
            document = frontmatter.load(path)
            metadata = document.metadata.pop("pomeari")
            post_form = PostForm(metadata["post_form"])
            targets = list(metadata["targets"])
        except (KeyError, TypeError, ValueError) as error:
            raise DraftError(f"Draft '{name}' has invalid Pomeari metadata.") from error

        if document.metadata:
            content = frontmatter.dumps(document)
        else:
            content = document.content

        return Draft(
            name=path.stem,
            content=content,
            post_form=post_form,
            targets=targets,
        )

    def list(self) -> Iterable[DraftSummary]:
        drafts = []
        for path in self.path.glob("*.md"):
            try:
                draft = self.load(path.stem)
            except DraftError as error:
                logging.warning("Unable to load draft %s: %s", path.name, error)
                continue

            updated_at = datetime.fromtimestamp(
                path.stat().st_mtime,
                timezone.utc,
            ).isoformat()
            drafts.append(
                DraftSummary(
                    name=draft.name,
                    post_form=draft.post_form,
                    updated_at=updated_at,
                )
            )

        drafts.sort(key=lambda draft: draft.updated_at, reverse=True)
        return drafts

    def delete(self, name: str):
        path = self._draft_path(name)
        if not path.exists():
            raise DraftNotFoundError(name)
        path.unlink()
