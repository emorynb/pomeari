from mistletoe.markdown_renderer import MarkdownRenderer


class PlaintextRenderer(MarkdownRenderer):
    """
    A plaintext mistletoe renderer. Useful for platforms that don't support
    text formatting.

    Inherits from Markdown as it's one of the rare markup languages designed to
    be readable when viewed as plaintext. TODO: actually implement it lol
    """

    pass
