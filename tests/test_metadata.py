from cs2mc.app_metadata import (
    CREATOR_NAME,
    DISCORD_USERNAME,
    GITHUB_URL,
    GITHUB_USERNAME,
)


def test_project_credit_and_repository_are_stable():
    assert CREATOR_NAME == "skrilll"
    assert GITHUB_USERNAME == "notskrillence"
    assert DISCORD_USERNAME == "skrilll"
    assert GITHUB_URL == "https://github.com/notskrillence/CS2-Music-Controller"
