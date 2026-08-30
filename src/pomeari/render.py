from mistletoe.markdown_renderer import MarkdownRenderer


class PlaintextRenderer(MarkdownRenderer):
    """Placeholder for a converter of Markdown-formatted rich text into plain
    text.

    This renderer is intended to convert Markdown into plain text for platforms
    that do not support rich text. ``MastodonPlatform`` currently uses it when
    preparing content for an instance believed not to support Markdown.

    Right now, this class inherits
    ``mistletoe.markdown_renderer.MarkdownRenderer`` unchanged, which means that
    it still renders Markdown syntax rather than stripping formatting. In the
    future, this functionality should get implemented.
    """

    pass
