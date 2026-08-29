from click.testing import CliRunner

import pomeari.cli as cli_module
from pomeari.service import PomeariService

from .helpers import ShortPlatform


def test_cli_publishes_through_service(tmp_path, monkeypatch):
    platform = ShortPlatform()

    def make_service():
        return PomeariService(tmp_path, {"short": platform})

    monkeypatch.setattr(cli_module, "PomeariService", make_service)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        ["post", "short", "--message", "A CLI post.", "--target", "short"],
    )

    assert result.exit_code == 0
    assert "Short platform (short): https://short.example/post" in result.output
    assert platform.posts[0][0] == "A CLI post."
