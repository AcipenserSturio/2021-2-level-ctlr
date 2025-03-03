"""
Pipeline for text processing implementation
"""
import re
from pathlib import Path

from pymorphy3 import MorphAnalyzer
from pymystem3 import Mystem

from constants import ASSETS_PATH
from core_utils.article import Article, ArtifactType


class EmptyDirectoryError(Exception):
    """
    No data to process
    """


class InconsistentDatasetError(Exception):
    """
    Corrupt data:
        - numeration is expected to start from 1 and to be continuous
        - a number of text files must be equal to the number of meta files
        - text files must not be empty
    """


class MorphologicalToken:
    """
    Stores language params for each processed token
    """

    def __init__(self, original_word):
        self.original_word = original_word
        self.normalized_form = ""
        self.tags_mystem = ""
        self.tags_pymorphy = ""

    def get_cleaned(self):
        """
        Returns lowercased original form of a token
        """
        return self.original_word.lower()

    def get_single_tagged(self):
        """
        Returns normalized lemma with MyStem tags
        """
        return f"{self.normalized_form}<{self.tags_mystem}>"

    def get_multiple_tagged(self):
        """
        Returns normalized lemma with PyMorphy tags
        """
        return f"{self.normalized_form}<{self.tags_mystem}>({self.tags_pymorphy})"


class CorpusManager:
    """
    Works with articles and stores them
    """

    def __init__(self, path_to_raw_txt_data: str):
        self.path_to_raw_text_data = path_to_raw_txt_data
        self._storage = {}
        self._scan_dataset()

    def _scan_dataset(self):
        """
        Register each dataset entry
        """
        for file in self.path_to_raw_text_data.glob("*_raw.txt"):
            index = _id_from_path(file)
            self._storage[index] = Article(None, index)

    def get_articles(self):
        """
        Returns storage params
        """
        return self._storage


class TextProcessingPipeline:
    """
    Process articles from corpus manager
    """

    def __init__(self, corpus_manager: CorpusManager):
        self.corpus_manager = corpus_manager

    def run(self):
        """
        Runs pipeline process scenario
        """
        for article in self.corpus_manager.get_articles().values():
            print(article.article_id)
            text = article.get_raw_text()
            tokens = self._process(text)
            article.save_as(" ".join(map(lambda x: x.get_cleaned(), tokens)),
                            ArtifactType.cleaned)
            article.save_as(" ".join(map(lambda x: x.get_single_tagged(), tokens)),
                            ArtifactType.single_tagged)
            article.save_as(" ".join(map(lambda x: x.get_multiple_tagged(), tokens)),
                            ArtifactType.multiple_tagged)



    def _process(self, raw_text: str):
        """
        Processes each token and creates MorphToken class instance
        """
        mystem = Mystem()
        morph_analyzer = MorphAnalyzer()
        # Linebreaks make Mystem slow and unresponsive.
        tokens = []
        for analysis in mystem.analyze(raw_text.replace("\n", " ")):
            if "analysis" not in analysis:
                continue
            if not analysis["analysis"]:
                continue
            token = MorphologicalToken(original_word=analysis["text"])

            token.normalized_form = analysis["analysis"][0]["lex"]
            token.tags_mystem = analysis["analysis"][0]["gr"]
            token.tags_pymorphy = morph_analyzer.parse(analysis["text"])[0].tag

            tokens.append(token)
        return tokens


def validate_dataset(path_to_validate):
    """
    Validates folder with assets
    """
    path = Path(path_to_validate)
    if not path.exists():
        raise FileNotFoundError
    if not path.is_dir():
        raise NotADirectoryError
    if not any(path.iterdir()):
        raise EmptyDirectoryError
    for file in path.iterdir():
        if not file.stat().st_size:
            raise InconsistentDatasetError("empty file")

    meta_ids = sorted(map(_id_from_path, path.glob("*_meta.json")))
    raw_ids = sorted(map(_id_from_path, path.glob("*_raw.txt")))

    if not all(map(lambda a: a[0] == a[1], zip(meta_ids, range(1, len(meta_ids) + 1)))):
        raise InconsistentDatasetError("meta files should be listed 1 to N")
    if not all(map(lambda a: a[0] == a[1], zip(raw_ids, range(1, len(meta_ids) + 1)))):
        raise InconsistentDatasetError("raw files should be listed 1 to N")
    if len(meta_ids) != len(raw_ids):
        raise InconsistentDatasetError("uneven number of meta and text files")


def _id_from_path(path):
    path_id = re.sub(r"[^0-9]", "", path.name)
    if not path_id.isdigit():
        raise InconsistentDatasetError("file name contains no id")
    return int(path_id)


def main():
    # YOUR CODE HERE
    validate_dataset(ASSETS_PATH)
    corpus_manager = CorpusManager(path_to_raw_txt_data=ASSETS_PATH)
    pipeline = TextProcessingPipeline(corpus_manager=corpus_manager)
    pipeline.run()


if __name__ == "__main__":
    main()
