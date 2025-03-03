"""
Scrapper implementation
"""

from datetime import datetime as dt
import json
from pathlib import Path
import re
import shutil

from bs4 import BeautifulSoup
import requests

from constants import (
    ASSETS_PATH,
    CRAWLER_CACHE_PATH,
    CRAWLER_CONFIG_PATH
)
from core_utils.article import Article
from core_utils.pdf_utils import PDFRawFile


class IncorrectURLError(Exception):
    """
    Seed URL does not match standard pattern
    """


class NumberOfArticlesOutOfRangeError(Exception):
    """
    Total number of articles to parse is too big
    """


class IncorrectNumberOfArticlesError(Exception):
    """
    Total number of articles to parse in not integer
    """


def _clean_text(text):
    return re.sub(r"[\n\t ]+", " ", text).strip()


def _get_page(link):
    response = requests.get(link)
    if not response.ok:
        return None
    return BeautifulSoup(response.text, "html.parser")


class Crawler:
    """
    Crawler implementation
    """

    def __init__(self, seed_urls, max_articles: int):
        self.seed_urls = seed_urls
        self.max_articles = max_articles
        self.urls = []

    def _extract_url(self, article_bs):
        if not article_bs:
            return
        for node in article_bs.find_all("a", {"class": "file"}):
            # ignore links to issues, only collect articles.
            # this does not leave out any content, because issues
            # are comprised of the same articles.
            if "issue" in node["href"]:
                continue
            if len(self.urls) == self.max_articles:
                break
            self._add_url(node["href"])

    def _add_url(self, href):
        self.urls.append(href)

    def find_articles(self):
        """
        Finds articles
        """
        for seed in self.seed_urls:
            if len(self.urls) == self.max_articles:
                break
            try:
                self._extract_url(_get_page(seed))
            except requests.exceptions.ConnectionError:
                continue

    def get_search_urls(self):
        """
        Returns seed_urls param
        """
        return self.seed_urls


class CrawlerRecursive(Crawler):
    def __init__(self, seed_urls, max_articles, cached=True):

        super().__init__(seed_urls, max_articles)
        self._crawled = set()
        self._cached = cached
        if self._cached:
            self.get_cache()

    def _add_url(self, href):
        print(len(self.urls))
        if self._cached:
            self.update_cache(href)
        self.urls.append(href)

    def get_cache(self):
        if not CRAWLER_CACHE_PATH.exists():
            return
        if not CRAWLER_CACHE_PATH.stat().st_size:
            return
        with open(CRAWLER_CACHE_PATH, encoding="utf-8") as file:
            self.urls = file.read().split("\n")
            self._crawled = set(self.urls)

    def update_cache(self, href):
        with open(CRAWLER_CACHE_PATH, "w", encoding="utf-8") as file:
            file.write("\n".join(self.urls))

    def find_articles(self):
        self.recurse(self.seed_urls.pop())

    def recurse(self, seed):
        if len(self.urls) >= self.max_articles:
            return
        if seed in self._crawled:
            return
        self._crawled.add(seed)

        try:
            page = _get_page(seed)
        except requests.exceptions.ConnectionError:
            return
        # if the page is an issue of articles, extract them
        if "showToc" in seed:
            self._extract_url(page)
            return
        # if the page is an archive of issues, recurse over them
        for link in page.find_all("a"):
            if "href" not in link.attrs:
                continue
            href = link.attrs["href"]
            if "archive" in seed:
                if "showToc" in href:
                    self.recurse(href)
            # also recurse over next pages in archive.
            # the order (issues before next page) matters for priority.
            if "archive" in href:
                self.recurse(href)


class HTMLParser:
    def __init__(self, article_url, article_id):
        self._pdf_url = article_url.replace("view", "download") + ".pdf"
        self.article_url = "/".join(article_url.split("/")[:-1])
        self.article_id = article_id
        self.article = Article(url=self._pdf_url, article_id=article_id)

    def parse(self):
        self._fill_article_with_text()
        article_bs = _get_page(self.article_url)
        self._fill_article_with_meta_information(article_bs)
        return self.article

    def _fill_article_with_text(self):
        pdf_raw = PDFRawFile(self._pdf_url, self.article_id)
        pdf_raw.download()
        self.article.text = pdf_raw.get_text()

    def _fill_article_with_meta_information(self, article_bs):
        self.article.article_id = self.article_id
        self.article.title = article_bs.find("h1").text

        author = article_bs.find("div", {"id": "authorString"}).find("a")
        self.article.author = _clean_text(author.text if author.text else author["title"])

        topics = article_bs.find("div", {"id": "articleSubject"}).find("div").children
        topics = [_clean_text(topic.text) for topic in topics]
        self.article.topics = [topic for topic in topics if topic and "," not in topic]

        date = "".join(re.findall(r"(?<=печат[ьи] )[0-9\.]*", self.article.text))[:-1]
        self.article.date = dt.strptime(date, "%d.%m.%Y")


def prepare_environment(base_path):
    """
    Creates ASSETS_PATH folder if not created and removes existing folder
    """
    assets = Path(base_path)
    if assets.exists():
        shutil.rmtree(assets)
    assets.mkdir(parents=True)


def validate_config(crawler_path: Path):
    """
    Validates given config
    """
    with open(crawler_path) as file:
        config = json.load(file)

    if "seed_urls" not in config:
        raise IncorrectURLError
    if "total_articles_to_find_and_parse" not in config:
        raise IncorrectNumberOfArticlesError

    seed_urls = config["seed_urls"]
    max_articles = config["total_articles_to_find_and_parse"]

    if not isinstance(max_articles, int) or max_articles <= 0:
        raise IncorrectNumberOfArticlesError
    if max_articles > 200:
        raise NumberOfArticlesOutOfRangeError
    if not isinstance(seed_urls, list) or not seed_urls:
        raise IncorrectURLError
    for seed_url in seed_urls:
        if not _is_valid_url(seed_url):
            raise IncorrectURLError

    return seed_urls, max_articles


def _is_valid_url(url_to_validate):
    return re.match(r"https?://", url_to_validate)


if __name__ == '__main__':
    seeds, limit = validate_config(CRAWLER_CONFIG_PATH)
    prepare_environment(ASSETS_PATH)
    crawler = CrawlerRecursive(seed_urls=seeds, max_articles=limit)
    crawler.find_articles()

    for index, url in enumerate(crawler.urls):
        parser = HTMLParser(article_url=url, article_id=index+1)
        article = parser.parse()
        article.save_raw()
