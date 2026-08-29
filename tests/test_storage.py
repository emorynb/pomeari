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
from pomeari.db import Database


def test_migrates_legacy_database_without_removing_it(tmp_path):
    async def scenario():
        legacy_path = tmp_path / "legacy.db"
        legacy = Database(legacy_path)
        await legacy.initialize()
        await legacy.set_config("example_key", "example value")

        data_dir = tmp_path / "data"
        async with PomeariService(
            data_dir=data_dir,
            platforms={},
            legacy_db_path=legacy_path,
        ) as service:
            assert await service.get_config() == {"example_key": "example value"}

        assert legacy_path.exists()
        assert (data_dir / "pomeari.db").exists()

    asyncio.run(scenario())


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
            assert len(summaries) == 1
            assert summaries[0].name == "an essay"

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
