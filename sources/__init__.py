from .aeon import AeonSource
from .base import Source
from .generic import GenericSource
from .psyche import PsycheSource

# Every source listed here gets built into docs/<slug>.xml and listed on
# the homepage. Order here = display order on the homepage.
SOURCES: list[Source] = [
    PsycheSource(),
    AeonSource(),
    # GenericSource(
    #     slug="example",
    #     name="Example Site",
    #     feed_url="https://example.com/feed.xml",
    #     site_url="https://example.com",
    #     description="Drop-in adapter using generic (trafilatura) extraction only.",
    # ),
]

__all__ = ["SOURCES", "Source", "PsycheSource", "AeonSource", "GenericSource"]
