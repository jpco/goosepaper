import datetime
import requests
import feedparser
import urllib.parse
from typing import List
from readability import Document

from .storyprovider import StoryProvider
from ..story import Story


class RSSFeedStoryProvider(StoryProvider):
    def __init__(
        self,
        rss_path: str,
        limit: int = 5,
        since_days_ago: int = None,
    ) -> None:
        self.limit = limit
        self.feed_url = rss_path
        self._since = (
            datetime.datetime.now() - datetime.timedelta(days=since_days_ago)
            if since_days_ago
            else None
        )

    def get_stories(self, limit: int = 5, **kwargs) -> List[Story]:
        feed = feedparser.parse(self.feed_url)
        limit = min(limit, self.limit, len(feed.entries))
        if limit == 0:
            print(f"Sad honk :/ No entries found for feed {self.feed_url}...")

        stories = []
        for entry in feed.entries:
            date = datetime.datetime(*entry.updated_parsed[:6])
            if self._since is not None and date < self._since:
                continue

            req = requests.get(entry["link"], headers={'User-Agent': 'goosepaper/0.7.1'})
            # Source is the URL root:
            source = urllib.parse.urlparse(entry["link"]).netloc
            if not req.ok:
                # Just return the headline content:
                story = Story(
                    entry["title"],
                    body_html=entry["summary"],
                    byline=source,
                    date=date,
                )
            elif req.content != b'':
                doc = Document(req.content)
                story = Story(
                    doc.title(),
                    body_html=doc.summary(),
                    byline=source,
                    date=date,
                )
            else:
                print(f"Sad honk :/ Empty response from feed {self.feed_url}...")
                continue

            stories.append(story)
            if len(stories) >= limit:
                break

        return list(filter(None, stories))
