"""
Useful constant variables
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
ASSETS_PATH = PROJECT_ROOT / 'tmp' / 'articles'
CRAWLER_CONFIG_PATH = PROJECT_ROOT / 'scrapper_config.json'
CRAWLER_CACHE_PATH = PROJECT_ROOT / 'cache.txt'
SECOND_PERSON_PATH = PROJECT_ROOT / '2sg.txt'
