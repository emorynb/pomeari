import asyncio

import pytest

from pomeari import (
    FavoritePlatformError,
    MissingConfigurationError,
    PomeariService,
    PostForm,
    PublishRequest,
    PublishStatus,
)

from .helpers import (
    ConfigUpdatingPlatform,
    ConfiguredShortPlatform,
    FailingLongPlatform,
    LongPlatform,
    ShortPlatform,
)


def test_lists_platform_capabilities_and_configuration(tmp_path):
    async def scenario():
        platforms = {
            "plain": ShortPlatform(),
            "configured": ConfiguredShortPlatform(),
            "long": LongPlatform(),
        }
        async with PomeariService(tmp_path, platforms) as service:
            initial = await service.list_platforms()
            assert [platform.configured for platform in initial] == [True, False, True]
            plain = initial[0]  # pyright: ignore[reportIndexIssue]
            long_info = initial[2]  # pyright: ignore[reportIndexIssue]
            assert plain.module is platforms["plain"].info
            assert plain.module.title == "Short platform"
            assert plain.supports_short is True
            assert plain.supports_long is False
            assert long_info.supports_long is True

            await service.set_config("short_token", "secret")
            configured = await service.list_platforms()
            assert all(platform.configured for platform in configured)

    asyncio.run(scenario())


def test_publishes_only_to_selected_platforms(tmp_path):
    async def scenario():
        selected = ShortPlatform("https://selected.example/post")
        unselected = ConfiguredShortPlatform()
        platforms = {"selected": selected, "unselected": unselected}

        async with PomeariService(tmp_path, platforms) as service:
            result = await service.publish(
                PublishRequest(
                    post_form=PostForm.SHORT,
                    content="A small test post.",
                    targets=("selected",),
                )
            )

            assert len(result.platforms) == 1
            assert result.platforms[0].platform == "selected"
            assert result.platforms[0].status == PublishStatus.SUCCESS
            assert len(selected.posts) == 1
            assert not unselected.posts

            history = await service.get_history()
            run = history[0]  # pyright: ignore[reportIndexIssue]
            assert run.posts[0].platform == "selected"

    asyncio.run(scenario())


def test_validates_configuration_for_selected_platforms(tmp_path):
    async def scenario():
        platform = ConfiguredShortPlatform()
        async with PomeariService(tmp_path, {"configured": platform}) as service:
            request = PublishRequest(
                post_form=PostForm.SHORT,
                content="A configured post.",
                targets=("configured",),
            )

            with pytest.raises(MissingConfigurationError) as caught:
                await service.publish(request)

            assert caught.value.entries[0].key == "short_token"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("post_form", "content"),
    [
        (PostForm.SHORT, "A short config-updating post."),
        (PostForm.LONG, "A long config-updating post."),
    ],
)
def test_persists_platform_config_updates(tmp_path, post_form, content):
    async def scenario():
        platform = ConfigUpdatingPlatform()
        async with PomeariService(tmp_path, {"updating": platform}) as service:
            await service.set_config("untouched", "same")
            await service.set_config("replaced", "old")
            if post_form == PostForm.LONG:
                await service.set_favorite_platform("updating")

            await service.publish(
                PublishRequest(
                    post_form=post_form,
                    content=content,
                    targets=("updating",),
                )
            )

            assert platform.posts[0][1] == {
                "untouched": "same",
                "replaced": "old",
                "added": "default",
            }
            assert await service.get_config() == {
                "untouched": "same",
                "replaced": "new",
                "added": "added",
            }

    asyncio.run(scenario())


def test_long_post_uses_favorite_then_relays_to_short_platform(tmp_path):
    async def scenario():
        primary = LongPlatform("https://long.example/an-essay")
        relay = ShortPlatform()
        platforms = {"primary": primary, "relay": relay}

        async with PomeariService(tmp_path, platforms) as service:
            await service.set_favorite_platform("primary")
            result = await service.publish(
                PublishRequest(
                    post_form=PostForm.LONG,
                    content="---\ntitle: An essay\n---\nThe essay body.",
                    targets=("primary", "relay"),
                )
            )

            assert [entry.status for entry in result.platforms] == [
                PublishStatus.SUCCESS,
                PublishStatus.SUCCESS,
            ]
            assert relay.posts[0][0] == ("An essay\n\nhttps://long.example/an-essay")

    asyncio.run(scenario())


def test_long_post_requires_the_favorite_target(tmp_path):
    async def scenario():
        platforms = {"primary": LongPlatform(), "other": LongPlatform()}

        async with PomeariService(tmp_path, platforms) as service:
            await service.set_favorite_platform("primary")
            request = PublishRequest(
                post_form=PostForm.LONG,
                content="A long post.",
                targets=("other",),
            )

            with pytest.raises(FavoritePlatformError):
                await service.publish(request)

    asyncio.run(scenario())


def test_failed_primary_skips_short_form_relays(tmp_path):
    async def scenario():
        relay = ShortPlatform()
        platforms = {"primary": FailingLongPlatform(), "relay": relay}

        async with PomeariService(tmp_path, platforms) as service:
            await service.set_favorite_platform("primary")
            result = await service.publish(
                PublishRequest(
                    post_form=PostForm.LONG,
                    content="A long post.",
                    targets=("primary", "relay"),
                )
            )

            assert result.platforms[0].status == PublishStatus.FAILED
            assert result.platforms[1].status == PublishStatus.SKIPPED
            assert not relay.posts

    asyncio.run(scenario())
