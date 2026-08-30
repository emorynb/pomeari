import asyncio

import frontmatter
import pytest

from pomeari import (
    Draft,
    DraftNotFoundError,
    InvalidDraftNameError,
    PomeariService,
    PostForm,
)


def test_saves_loads_lists_and_deletes_markdown_drafts(tmp_path):
    async def scenario():
        async with PomeariService(tmp_path, {}) as service:
            draft = Draft(
                name="an essay",
                content="---\ntitle: An essay\n---\nThe draft body.",
                post_form=PostForm.LONG,
                targets=["primary", "relay"],
            )
            await service.save_draft(draft)

            loaded = await service.load_draft("an essay")
            loaded_document = frontmatter.loads(loaded.content)
            assert loaded.name == draft.name
            assert loaded.post_form == PostForm.LONG
            assert loaded.targets == draft.targets
            assert loaded_document["title"] == "An essay"
            assert loaded_document.content == "The draft body."

            summaries = await service.list_drafts()
            assert len(summaries) == 1  # pyright: ignore[reportArgumentType]
            assert summaries[0].name == "an essay"  # pyright: ignore[reportIndexIssue]

            await service.delete_draft("an essay")
            with pytest.raises(DraftNotFoundError):
                await service.load_draft("an essay")

    asyncio.run(scenario())


def test_rejects_draft_paths(tmp_path):
    async def scenario():
        async with PomeariService(tmp_path, {}) as service:
            draft = Draft(
                name="../outside",
                content="Content",
                post_form=PostForm.SHORT,
                targets=[],
            )

            with pytest.raises(InvalidDraftNameError):
                await service.save_draft(draft)

    asyncio.run(scenario())
