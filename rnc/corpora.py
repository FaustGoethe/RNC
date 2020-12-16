__all__ = (
    'MainCorpus',
    'DialectalCorpus',
    'AccentologicalCorpus',
    'SpokenCorpus',
    'PaperRegionalCorpus',
    'Paper2000Corpus',
    'ParallelCorpus',
    'MultilingualParaCorpus',
    'TutoringCorpus',
    'MultimodalCorpus',

    'SORT_KEYS',
    'SEARCH_FORMATS',
    'OUTPUT_FORMATS'
)

import csv
import json
import logging
import os
import random
import re
import string
import time
import webbrowser
from pathlib import Path
from typing import Dict, Callable, List, Any, Tuple
from urllib.parse import unquote

import bs4

import rnc.corpora_requests as creq
import rnc.examples as expl

logger = logging.getLogger("rnc")


# Russian National Corpus URL
RNC_URL = "https://processing.ruscorpora.ru/search.xml"
BASE_RNC_URL = "https://processing.ruscorpora.ru"

ALPHABET = f"{string.ascii_letters}{string.digits}"


SORT_KEYS = (
    'i_grtagging', 'random', 'i_grauthor', 'i_grcreated_inv',
    'i_grcreated', 'i_grbirthday_inv', 'i_grbirthday',
)
SEARCH_FORMATS = (
    'lexform', 'lexgramm'
)
OUTPUT_FORMATS = (
    'normal', 'kwic'
)


def create_filename(length: int = 8) -> str:
    """ Create random filename.

    :param length: int, length of result (8 by default).
    :return: str, random symbols.
    """
    name = random.sample(ALPHABET, length)
    return ''.join(name)


def create_unique_filename(folder: Path,
                           class_name: str,
                           p_count: int) -> Path:
    """ Create a random unique csv filename,
    means the file does not exist.

    Name format:
    <class_name><p_count>_<some random symbols>

    :param folder: Path to the data folder.
    :param class_name: name of the class.
    :param p_count: int, count of pages.
    :return: Path, unique filename.
    """
    name_template = "{}{}_{}.csv"
    name = name_template.format(class_name, p_count, create_filename())
    path = folder / name
    while path.exists():
        name = name_template.format(class_name, p_count, create_filename())
        path = path.with_name(name)
    return path


def clean_text_up(text: str) -> str:
    """ Remove duplicate spaces from str and strip it.

    :param text: str to clean up.
    :return: str, clean str.
    """
    return ' '.join(text.split()).strip()


def create_doc_url(doc_url: str) -> str:
    """ Create full url to document in RNC.
    Add https://... to doc.

    :param doc_url: str, doc url to extend.
    :return: str, extended url.
    """
    if not doc_url:
        return doc_url
    return f"{BASE_RNC_URL}/{doc_url}"


def join_with_plus(item: str) -> str:
    """ Split txt and join it with '+'.

    :param item: str, text to convert.
    :return: str, converted text.
    """
    res = item.split()
    return '+'.join(res)


def str_to_int(value: str) -> int:
    """ Convert str like '350 000 134' to int.

    :param value: str to convert.
    :return: int.
    """
    return int(value.replace(' ', ''))


class Corpus:
    """ Base class for Corpora """
    # default params
    # documents per page
    __DPP = 5
    # sentences per document
    __SPD = 10
    # search format
    __TEXT = 'lexgramm'
    # output format
    __OUT = 'normal'
    # accent on words
    __ACCENT = '0'
    # show order
    __SORT = 'i_grtagging'
    # distance between n and (n + 1) words
    __MIN = 1
    __MAX = 3
    # count of examples to print
    __RESTRICT_SHOW = 50

    # symbols to write csv
    _DATA_W_DELIMITER = '\t'
    _DATA_W_QUOTCHAR = '"'

    DATA_FOLDER = Path('data')

    def __init__(self,
                 query: dict or str = None,
                 p_count: int = None,
                 file: str or Path = None,
                 **kwargs) -> None:
        """ 
        If the file exists, working with a local database.

        :param query: dict of str, words to search;
         {word1: {properties}, word2: {properties}...}.
         If you chose 'lexform' as a 'text' param, you must give here a string.
        :param p_count: int, count of pages to request.
        :param file: str or Path, filename of a local database.
         Optional, random filename by default.
        :keyword dpp: str or int, documents per page.
         Optional, 5 by default.
        :keyword spd: str or int, sentences per document.
         Optional, 10 by default.
        :keyword text: str, search format: 'lexgramm' or 'lexform'.
         Optional, 'lexgramm' by default.
        :keyword out: str, output format: 'normal' or 'kwic'.
         Optional, 'normal' bu default.
        :keyword kwsz: str or int, count of words in context;
         Optional param if 'out' is 'kwic'.
        :keyword sort: str, sort show order. See docs how to set it.
         Optional.
        :keyword mycorp: str, mycorp. This is way to specify the sample of docs
         where you want to find sth. See docs how to set it. Optional.
        :keyword expand: str, if 'full', all part of doc will be shown. 
         Now it doesn't work.
        :keyword accent: str or int, with accents on words or not:
         1 – with, 0 – without. Optional, 0 by default.
        :keyword marker: function, with which found words will be marked.
         Optional.

        :return: None.
        :exception FileExistsError: if csv file is given but json file
         with config doesn't exist.
        :exception ValueError: if the query is empty; page count is a negative 
         number; text, out or sort key is wrong.
        :exception NotImplementedError: if the corpus type in file isn't equal 
         to corpus class type.
        """
        # list of examples
        self._data = []
        # http tags to request
        self._params = {}
        # found wordforms with their frequency
        self._found_wordforms = {}
        # query, wordforms to find
        self._query = {}
        # count of PAGES
        self._p_count = 0
        # type of example should be defined before params init
        self._ex_type = kwargs.pop('ex_type', None)
        self._marker = kwargs.pop('marker', None)
        # additional info from the first page:
        # amount of docs, contexts, where the query was found,
        # link to the graphic with distribution by years
        self._add_info = {}

        # path to local database
        class_name = self.__class__.__name__.replace('Corpus', '')
        path = Path(file) or create_unique_filename(
            self.DATA_FOLDER, class_name, p_count)

        # change or add right extension
        path = path.with_suffix('.csv')

        # to these files the data and req params will be dumped
        self._csv_path = path
        self._config_path = path.with_suffix('.json')

        # init from file if it exists
        if self._csv_path.exists():
            try:
                self._from_file()
            except FileExistsError:
                logger.exception('')
                raise
        # or work with RNC
        else:
            self._from_corpus(query, p_count, **kwargs)

    def _from_corpus(self,
                     query: dict or str,
                     p_count: int,
                     **kwargs) -> None:
        """ Set given values to the object. If the file does not exist.
        Params the same as in the init method.

        :return: None.
        :exception ValueError: if the query is empty; pages count is a negative
         number; out, sort, text key is wrong.
        """
        if not query:
            msg = "Query must be not empty"
            logger.error(msg)
            raise ValueError(msg)
        self._query = query

        if p_count <= 0:
            msg = "Page count must be > 0"
            logger.error(msg)
            raise ValueError(msg)
        self._p_count = p_count

        # base params
        self._params['env'] = 'alpha'
        self._params['api'] = '1.0'
        self._params['lang'] = 'en'

        self._params['dpp'] = kwargs.pop('dpp', None) or self.__DPP
        self._params['spd'] = kwargs.pop('spd', None) or self.__SPD
        self._params['text'] = kwargs.pop('text', None) or self.__TEXT
        self._params['out'] = kwargs.pop('out', None) or self.__OUT
        self._params['sort'] = kwargs.pop('sort', None) or self.__SORT

        msg = "'{}' is wrong {} value, expected: {}"
        if self.params['text'] not in SEARCH_FORMATS:
            msg = msg.format(self.params['text'], 'text', SEARCH_FORMATS)
            logger.error(msg)
            raise ValueError(msg)
        if self.params['out'] not in OUTPUT_FORMATS:
            msg = msg.format(self.params['out'], 'out', OUTPUT_FORMATS)
            logger.error(msg)
            raise ValueError(msg)
        if self.params['sort'] not in SORT_KEYS:
            msg = msg.format(self.params['sort'], 'sort', SORT_KEYS)
            logger.error(msg)
            raise ValueError(msg)

        accent = kwargs.pop('accent', None) or self.__ACCENT
        accent = int(accent)
        self._params['nodia'] = int(not accent)

        if self.params['out'] == 'kwic' and 'kwsz' in kwargs:
            self._params['kwsz'] = kwargs.pop('kwsz')

        if 'mycorp' in kwargs:
            mycorp = kwargs.pop('mycorp')
            self._params['mycorp'] = urllib.parse.unquote(mycorp)

        # TODO: page structure changed if expand=full
        # if 'expand' in kwargs:
        #     self._params['expand'] = kwargs.pop('expand')

        self._query_to_http()

        # parsing depends on 'out' value
        self._page_parser = None
        self._page_parser_and_ex_type()

    def _from_file(self) -> None:
        """ Load data and params from the local databases.
        If the file exists.

        :return: None.
        """
        if not (self._csv_path.exists() and self._config_path.exists()):
            raise FileExistsError("Data and config file must exist together")

        params = self._load_params()
        self._query = params.get('query', None)
        self._p_count = params.get('p_count', None)
        self._params = params.get('params', None)

        mode = self.mode
        if mode is None or mode != self._MODE:
            msg = f"Tried to load data to wrong Corpus: " \
                  f"{mode} instead of {self._MODE}"
            logger.error(msg)
            raise NotImplementedError(msg)

        # these params must be defined here too
        self._page_parser_and_ex_type()

        self._data = self._load_data()
        # add info about
        try:
            self._get_additional_info()
        except Exception:
            logger.exception("It is impossible to get additional info from RNC")

    def _load_data(self) -> List:
        """ Load data from csv file.

        :return: list of examples.
        """
        with self.file.open('r', encoding='utf-8') as f:
            dm = self._DATA_W_DELIMITER
            qch = self._DATA_W_QUOTCHAR
            reader = csv.reader(f, delimiter=dm, quotechar=qch)
            # first row contains headers, skip it
            next(reader)

            data = [self.ex_type(*row) for row in reader]
            wordforms = list(map(lambda example: example.found_wordforms, data))
            wordforms = sum(wordforms, [])
            self._add_wordforms(wordforms)

        return data

    def _load_params(self) -> Dict:
        """ Load request params from json file.

        :return: json dict.
        """
        with self._config_path.open('r', encoding='utf-8') as f:
            return json.load(f)

    @classmethod
    def set_dpp(cls, value: int) -> None:
        if not isinstance(value, int) or value <= 0:
            logger.error("DPP must be int > 0")
            raise ValueError("DPP must be int > 0")
        cls.__DPP = value

    @classmethod
    def set_spd(cls, value: int) -> None:
        if not isinstance(value, int) or value <= 0:
            logger.error("SPD must be int > 0")
            raise ValueError("SPD must be int > 0")
        cls.__SPD = value

    @classmethod
    def set_text(cls, value: str) -> None:
        if value not in SEARCH_FORMATS:
            msg = f"Valid search formats: {SEARCH_FORMATS}, '{value}' was given"
            logger.error(msg)
            raise ValueError(msg)

        cls.__TEXT = value

    @classmethod
    def set_sort(cls, value: str) -> None:
        if value not in SORT_KEYS:
            msg = f"Valid sort keys: {SORT_KEYS}, '{value}' was given"
            logger.error(msg)
            raise ValueError(msg)

        cls.__SORT = value

    @classmethod
    def set_out(cls, value: str) -> None:
        if value not in OUTPUT_FORMATS:
            msg = f"Valid out formats: {OUTPUT_FORMATS}, '{value}' was given"
            logger.error(msg)
            raise ValueError(msg)

        cls.__OUT = value

    @classmethod
    def set_min(cls, value: int) -> None:
        if not isinstance(value, int) or value <= 0:
            logger.error("min must be int > 0")
            raise ValueError("min must be int > 0")
        cls.__MIN = value

    @classmethod
    def set_max(cls, value: int) -> None:
        if not isinstance(value, int) or value <= 0:
            logger.error("max must be int > 0")
            raise ValueError("max must be int > 0")
        cls.__MAX = value

    @classmethod
    def set_restrict_show(cls, value: int or bool) -> None:
        if not isinstance(value, (int, bool)):
            logger.error("Restrict count must be int or bool")
            raise TypeError("Restrict count must be int or bool")
        cls.__RESTRICT_SHOW = value

    @staticmethod
    def _get_ambiguation(tag: bs4.element.Tag) -> str:
        """ Get pretty ambiguation from example.

        :param tag: bs4.element.Tag, example.
        :return: str, 'disambiguated' or 'not disambiguated' or 'Not found'.
        """
        ambiguation = (tag.find('span', {'class': 'on'}) or
                       tag.find('span', {'class': 'off'}))
        if not ambiguation:
            return 'Not found'
        ambiguation = ambiguation.text.strip()
        # here ambiguation like '[...]'
        ambiguation = ambiguation[1:-1].strip()
        return ambiguation

    @staticmethod
    def _get_text(tag: bs4.element.Tag) -> str:
        """ Get pretty text from example and remove
        from there duplicate spaces.

        Here it is assumed, that all examples have text.

        :param tag: bs4.element.Tag, example.
        :return: str, text.
        """
        # using 'findall' method removes punctuation marks
        txt = tag.get_text()
        # remove duplicate spaces
        return clean_text_up(txt)

    @staticmethod
    def _get_doc_url(tag: bs4.element.Tag) -> str:
        """ Get pretty doc url from example.

        :param tag: bs4.element.Tag, example.
        :return: str, doc url or 'Not found'.
        """
        doc_url = tag.a
        if not doc_url:
            return 'Not found'
        doc_url = doc_url.attrs['href']
        return create_doc_url(doc_url)

    @staticmethod
    def _get_source(tag: bs4.element.Tag) -> str:
        """ Get pretty source from example.

        :param tag: bs4.element.Tag, example.
        :return: str, examples source or 'Not found'.
        """
        src = tag.find('span', {'class': 'doc'})
        if not src:
            return "Not found"
        src = clean_text_up(src.text)
        # here src like '[...]'
        src = src[1:-1].strip()
        return src

    @staticmethod
    def _parse_lexgramm_params(params: dict or str,
                               join_inside_symbol: str,
                               with_braces: bool = False) -> str:
        """ Convert lexgramm params to str for HTTP request.

        :param params: dict, params to convert.
        :param join_inside_symbol: str, symbol to join params.
        :param with_braces: bool, whether the braces 
        will be added around the param.
        :return: str, joined with ',' params.
        """
        if not (isinstance(params, (str, dict)) and ' ' not in params):
            msg = f"Param must be str without spaces or dict, given: {params}"
            logger.error(msg)
            raise ValueError(msg)
        # let the user to give only one param:
        # {'word': {'gramm': 'acc', 'flags': 'bmark'}}
        if isinstance(params, str):
            return params

        res = []
        for val in params.values():
            if not isinstance(val, (str, int, list)):
                msg = "One should give to tags only str, list or int"
                logger.error(msg)
                raise ValueError(msg)

            if isinstance(val, (str, int)):
                val = [str(val)]

            item = f"{'(' * with_braces}" \
                   f"{join_inside_symbol.join(val)}" \
                   f"{')' * with_braces}"
            res += [item]
        return ','.join(res)

    @staticmethod
    def _find_searched_words(tag: bs4.element.Tag) -> List[str]:
        """ Get searched words from tag, they are marked with 'g-em'
        parameter in the class name. Strip them.

        :param tag: bs4.element.Tag, tag with result.
        :return: list of string, words to which request was.
        """
        # TODO: simplify
        # params of the classes and word if 'class' is
        class_params = [
            (i.attrs.get('class', ''), i.text)
            for i in tag.contents
            if isinstance(i, bs4.element.Tag)
        ]
        # searched words are marked by class parameter 'g-em'
        searched_words = [
            i[1].strip()
            for i in class_params
            if 'g-em' in i[0]
        ]
        return searched_words

    @property
    def data(self) -> List:
        """
        :return: list of examples.
        """
        return self._data

    @property
    def query(self) -> Dict[str, dict] or str:
        """
        :return: dict or str, requested items.
        """
        return self._query

    @property
    def forms_in_query(self) -> List[str]:
        """
        :return: list of str, requested words.
        """
        req = self.query
        if isinstance(req, str):
            return req.split()
        return list(req.keys())

    @property
    def p_count(self) -> int:
        """
        :return: int, requested count of pages.
        """
        return self._p_count

    @property
    def file(self) -> Path:
        """
        :return: Path, path to local database file.
        """
        return self._csv_path

    @property
    def marker(self) -> Callable:
        """
        :return: function to mark found wordforms.
        """
        return self._marker

    @property
    def params(self) -> dict:
        """
        :return: dict of HTTP params.
        """
        return self._params

    @property
    def found_wordforms(self) -> dict:
        """ Get info about found wordforms, {form: frequency}.

        :return: dict of str, found wordforms and their frequency.
        """
        return self._found_wordforms

    @property
    def url(self) -> str:
        """ Return URL, first page of RNC results.

        :return: str, URL.
        """
        params = '&'.join(
            f"{key}={val}"
            for key, val in self.params.items()
        )
        return f"{RNC_URL}?{params}"

    @property
    def ex_type(self) -> Any:
        """
        :return: example type of the Corpus.
        """
        return self._ex_type

    @property
    def amount_of_docs(self) -> int or None:
        """ Get amount of documents, where the query was found.

        :return: int, this amount or None if it does not exist.
        """
        return self._add_info.get('docs', None)

    @property
    def amount_of_contexts(self) -> int or None:
        """ Get amount of contexts, where the query was found.

        :return: int, this amount or None if it does not exist.
        """
        return self._add_info.get('contexts', None)

    @property
    def graphic_link(self) -> str or None:
        """ Get the link the graphic of the
        distribution of query occurrences by years.

        :return: str, this link or None if it does not exist.
        """
        return self._add_info.get('graphic_link', None)

    def open_graphic(self) -> None:
        """ Open the graph of the distribution
        of query occurrences by years.

        :return: None.
        """
        url = self.graphic_link
        if url is None:
            msg = "Graphic does not exist"
            logger.error(msg)
            raise RuntimeError(msg)

        try:
            webbrowser.open_new_tab(url)
        except Exception:
            logger.exception("It is impossible to open the graphic")
            raise

    @staticmethod
    def _get_where_query_found(content: bs4.element.Tag) -> Dict[str, Any]:
        """ Get converted to int amount of found docs and contexts.

        :param content: bs4.element.Tag, here these values are.
        """
        res = {}
        amount = content.find('p', {'class': 'found'})
        blocks = amount.find_all('span', {'class': 'stat-number'})

        contexts = blocks[-1].get_text()
        res['contexts'] = str_to_int(contexts)
        if len(blocks) is 2:
            docs = blocks[0].get_text()
            res['docs'] = str_to_int(docs)
        return res

    @staticmethod
    def _get_graphic_url(content: bs4.element.Tag) -> str or None:
        """ Get distribution by years graphic URL.

        :param content: bs4.element.Tag, here the link is.
        :return: str, full URL.
        """
        a = content.find('a', {'target': '_blank'})
        try:
            link = a['href']
        except Exception:
            return
        return f"{BASE_RNC_URL}/{link}"

    def _get_additional_info(self) -> None:
        """ Get additional info (amount of found docs and contexts,
        link to graphic with distribution by years).

        :return: None.
        """
        params = self.params.copy()
        params['lang'] = 'ru'
        params.pop('expand', None)
        try:
            first_page_code = creq.get_htmls(RNC_URL, **params)[0]
        except Exception:
            raise

        soup = bs4.BeautifulSoup(first_page_code, 'lxml')
        content = soup.find('div', {'class': 'content'})

        additional_info = Corpus._get_where_query_found(content)
        graphic_url = Corpus._get_graphic_url(content)
        if graphic_url:
            additional_info['graphic_link'] = graphic_url

        self._add_info = additional_info.copy()

    def _page_parser_and_ex_type(self) -> None:
        """ Add 'parser' and 'ex_type' params.
        They are depended on 'out' tag.

        :return: None
        """
        if self.out == 'normal':
            # ex_type is defined above in this case
            self._page_parser = self._parse_page_normal
        elif self.out == 'kwic':
            self._page_parser = self._parse_page_kwic
            self._ex_type = expl.KwicExample

    def _query_to_http(self) -> None:
        """ Convert the query to HTTP tags, add them to params.

        :return: None.
        :exception ValueError: if the query is not str however out is lexform;

        :exception AssertionError:
        """
        if self.text == 'lexform':
            if not isinstance(self.query, str):
                msg = "Query must be str if search is 'lexform'"
                logger.error(msg)
                raise ValueError(msg)
            self._params['req'] = join_with_plus(self.query)

        # in lexgramm search one word may be too
        if isinstance(self.query, str):
            # working with long query like
            # 'открыть -открыл дверь -двери настеж'
            q = re.finditer(r'\b\w+\b( -\b\w+\b)?', self.query)
            for num, query in enumerate(q, 1):
                match = query.group(0)
                self._params[f"lex{num}"] = join_with_plus(match)
                if num > 1:
                    self._params[f"min{num}"] = self.__MIN
                    self._params[f"max{num}"] = self.__MAX
            return

        # words and their params
        for word_num, (word, params) in enumerate(self.query.items(), 1):
            # add distance
            if word_num > 1:
                min_distance = f'min{word_num}'
                max_distance = f'max{word_num}'
                # given or default values
                if isinstance(params, dict):
                    self._params[min_distance] = params.get('min', None) or self.__MIN
                    self._params[max_distance] = params.get('max', None) or self.__MAX
                else:
                    self._params[min_distance] = self.__MIN
                    self._params[max_distance] = self.__MAX

            self._params[f"lex{word_num}"] = join_with_plus(word)

            if isinstance(params, str):
                # empty param, skip it
                continue

            # grammar properties
            gramm = params.pop('gramm', '')
            if gramm:
                try:
                    gram_props = Corpus._parse_lexgramm_params(gramm, '|', True)
                except Exception:
                    raise
                self._params[f"gramm{word_num}"] = gram_props

            # additional properties
            flags = params.pop('flags', '')
            if flags:
                try:
                    flag_prop = Corpus._parse_lexgramm_params(flags, '+')
                except Exception:
                    raise
                self._params[f"flags{word_num}"] = flag_prop

            # TODO: semantic properties
            sem = params.pop('sem', '')
            if sem:
                logger.warning("Semantic properties does not support")

            if params:
                msg = f"Oops, 'gramm', 'flags' and 'sem' were expected, but " \
                      f"another keys given: {params}"
                logger.error(msg)
                raise ValueError(msg)

    def _add_wordforms(self,
                       forms: List[str]) -> None:
        """ Add found wordforms to counter. Low and strip items.

        :param forms: list of str, wordforms to add.
        :return: None.
        """
        if not forms:
            return

        for form in forms:
            form = clean_text_up(form).lower()
            self._found_wordforms[form] = self.found_wordforms.get(form, 0) + 1

    def _parse_doc(self,
                   doc: bs4.element.Tag) -> Any:
        """ Parse the doc to list of Examples.

        Parsing depends on the subcorpus,
        the method redefined at the descendants.
        """
        # TODO: remake this func to generator?
        msg = "The func not implemented to the parent Corpus class"
        logger.error(msg)
        raise NotImplementedError(msg)

    def _parse_example(self,
                       *args,
                       **kwargs) -> Any:
        """ Parse the example to Example object.

        Parsing depends on the subcorpus,
        the method redefined at the descendants.
        """
        msg = "The func not implemented to the parent Corpus class"
        logger.error(msg)
        raise NotImplementedError(msg)

    def _parse_kwic_example(self,
                            left: bs4.element.Tag,
                            center: bs4.element.Tag,
                            right: bs4.element.Tag) -> expl.KwicExample:
        l_txt = clean_text_up(left.text)
        c_txt = clean_text_up(center.text)
        # remove ←…→ symbol too
        r_txt = clean_text_up(right.text)[:-4].rstrip()

        found_wordforms = Corpus._find_searched_words(left)
        found_wordforms += Corpus._find_searched_words(center)
        found_wordforms += Corpus._find_searched_words(right)

        try:
            src = right.a.attrs['msg'].strip()
            url = right.a.attrs['href']
        except Exception:
            logger.exception("Source or url not found")
            src = url = ''

        url = create_doc_url(url)

        new_ex = expl.KwicExample(
            l_txt, c_txt, r_txt, src, found_wordforms, url)
        new_ex.mark_found_words(self.marker)

        return new_ex

    def _parse_page_kwic(self,
                         page: str) -> List[expl.KwicExample]:
        """ Parse page if 'out' is 'kwic'.

        :param page: str, html code of page to parse.
        :return: list of examples.
        :exception ValueError: if the content not found.
        """
        soup = bs4.BeautifulSoup(page, 'lxml')
        res = []

        content = soup.find('table', {'align': 'left'})
        if not content:
            msg = "Content is None, this behavior is undefined, contact the developer"
            logger.error(msg)
            raise ValueError(msg)

        nobr = content.find_all('nobr')
        if len(nobr) % 3:
            logger.warning("Len of nobr tags list % 3 != 0")

        for left, center, right in zip(nobr[::3], nobr[1::3], nobr[2::3]):
            new_ex = self._parse_kwic_example(left, center, right)
            res += [new_ex]
            self._add_wordforms(new_ex.found_wordforms)
        return res

    def _parse_page_normal(self,
                           page: str) -> List:
        """ Parse page if 'out' is 'normal'.

        :param page: str, html code to parse.
        :return: list of examples.
        """
        soup = bs4.BeautifulSoup(page, 'lxml')
        res = []

        for doc in soup.find_all('li'):
            try:
                parsed_doc = self._parse_doc(doc)
            except Exception:
                logger.exception("Error while parsing doc")
            else:
                res += parsed_doc

        return res

    def _parse_all_pages(self,
                         pages: List[str]) -> List:
        """ Parse all pages.

        :param pages: list of str, html codes of the pages.
        :return: list of examples.
        """
        parsed = [self._page_parser(page) for page in pages]
        return sum(parsed, [])

    def _data_to_csv(self) -> None:
        """ Dump the data to csv file.
        Here it is assumed that the data exist.

        :return: None.
        """
        data = [example.items for example in self.data]
        columns = self[0].columns
        with self.file.open('w', encoding='utf-8', newline='') as f:
            # class constants
            dm = self._DATA_W_DELIMITER
            qch = self._DATA_W_QUOTCHAR

            writer = csv.writer(
                f, delimiter=dm, quotechar=qch, quoting=csv.QUOTE_MINIMAL)
            writer.writerows([columns] + data)

    def _params_to_json(self) -> None:
        """ Write the request params: query,
        p_count and http tags to json file.

        Here it is assumed that these params exist.

        :return: None.
        """
        to_write = {
            'query': self.query,
            'p_count': self.p_count,
            'params': self.params
        }
        with self._config_path.open('w', encoding='utf-8') as f:
            json.dump(to_write, f, indent=4, ensure_ascii=False)

    def dump(self) -> None:
        """ Write the data to csv file, request params to json file.

        :return: None.
        :exception RuntimeError: If there are no data, params or files exist.
        """
        if not self.data:
            logger.error("There is no data to write")
            raise RuntimeError("There is no data to write")
        if not (self.query and self.p_count and self.params):
            logger.error("There is no data to write")
            raise RuntimeError("There is no data to write")

        os.makedirs(self.DATA_FOLDER, exist_ok=True)

        self._data_to_csv()
        self._params_to_json()

        logger.debug(
            f"Data was wrote to files: {self.file} and {self._config_path}")

    def open_url(self) -> None:
        """ Open first page of RNC results in the new
        tab of the default browser.

        :return: None.
        :exception ValueError: if url is wrong.
        :exception: if sth went wrong.
        """
        try:
            webbrowser.open_new_tab(self.url)
        except Exception:
            logger.exception(
                f"Error while opening doc with url: {self.url}")
            raise

    def request_examples(self) -> None:
        """ Request examples, parse them and update the data.

        If there are no results found, last page does not exist,
        params or query is wrong then exception.

        :return: None.

        :exception RuntimeError: if the data still exist.
        """
        if self.data:
            logger.error("Tried to request new examples, however data exist")
            raise RuntimeError("Data still exist")

        try:
            # TODO: get first page code if everything is OK
            creq.is_request_correct(RNC_URL, self.p_count, **self.params)
        except Exception:
            msg = f"Query = {self.forms_in_query}, {self.p_count}, {self.params}"
            logger.exception(msg)
            raise

        # get additional info from the first RNC page.
        logger.info("Requesting additional info from the first RNC page")
        self._get_additional_info()
        logger.info("Additional info was successfully received")

        logger.info("Main request")
        coro_start = time.time()
        htmls = creq.get_htmls(RNC_URL, 0, self.p_count, **self.params)
        logger.info("Main request was successfully completed")
        logger.info(f"Coro executing time: {time.time() - coro_start:.2f}")

        logger.info("Parsing html was started")
        try:
            parsing_start = time.time()
            parsed = self._parse_all_pages(htmls)
            parsing_stop = time.time()
        except Exception:
            logger.exception(f"Error while parsing, query = {self.params}")
            raise
        else:
            logger.info("Parsing was successfully completed")
            logger.info(f"Parsing time: {parsing_stop - parsing_start:.2f}")
            logger.info(f"Overall time: {parsing_stop - coro_start:.2f}")
            self._data = parsed[:]

    def copy(self) -> Any:
        """
        :return: copied object.
        """
        copy_obj = self.__class__(
            self.query, self.p_count, file=self.file, marker=self.marker, **self.params)
        copy_obj._data = self.data.copy()
        return copy_obj

    def sort_data(self,
                  **kwargs) -> None:
        """ Sort the data by using a key.

        :keyword key: func to sort, called to Example objects, by default – len.
        :keyword reverse: bool, whether the data will sort in reversed order,
         by default – False.
        :return None.
        :exception TypeError: if the key is uncallable.
        """
        key = kwargs.pop('key', lambda example: len(example))
        reverse = kwargs.pop('reverse', False)

        if not callable(key):
            logger.error("Given uncallable key to sort")
            raise TypeError("Sort key must be callable")
        self._data.sort(key=key, reverse=reverse)

    def pop(self,
            index: int) -> Any:
        """ Remove and return element from data at the index.

        :param index: int, index of the element.
        :return: Example object.
        """
        return self._data.pop(index)

    def shuffle(self) -> None:
        """ Shuffle list of examples.
        :return: None.
        """
        random.shuffle(self._data)

    def clear(self) -> None:
        """ Clear examples list.

        :return: None.
        """
        self._data.clear()

    def filter(self,
               key: Callable) -> None:
        """ Remove some items, that are not satisfied the key.

        :param key: callable, it will be used to Example
        objects inside the data list.
        :return: None.
        """
        filtered_data = list(filter(key, self.data))
        self._data = filtered_data[:]

    def findall(self,
                pattern: Any) -> None:
        """ Apply the pattern to the examples' text with re.findall.
        Change tha data list.

        :param pattern: r str or re.pattern, pattern to apply.
        :return: None.
        """
        pass

    def finditer(self,
                 pattern: Any) -> None:
        """ Apply the pattern to the examples' text with re.findall.
        Change tha data list.

        :param pattern: r str or re.pattern, pattern to apply.
        :return: None.
        """
        pass

    def __repr__(self) -> str:
        """ Format:
                Classname
                Length
                Database filename
                Request params
                Pages count
                Request

        :return: str with the format.
        """
        res = (f"{self.__class__.__name__}\n"
               f"{len(self)}\n" 
               f"{self.file}\n" 
               f"{self.params}\n" 
               f"{self.p_count}\n"
               f"{self.query}\n")
        return res

    def __str__(self) -> str:
        """
        :return: str, info about Corpus and enumerated examples.
        """
        q_forms = ', '.join(self.forms_in_query)
        metainfo = f"Russian National Corpus (https://ruscorpora.ru)\n" \
                   f"Class: {self.__class__.__name__}, len = {len(self)}\n" \
                   f"Pages: {self.p_count} of '{q_forms}' requested"

        data = self.data
        is_restricted = False
        if self.__RESTRICT_SHOW is not False and \
                len(data) > self.__RESTRICT_SHOW:
            data = self.data[:self.__RESTRICT_SHOW]
            is_restricted = True

        examples = '\n\n'.join(
            f"{num}.\n{str(example)}"
            for num, example in enumerate(data, 1)
        )
        if is_restricted:
            examples += '\n...'

        return f"{metainfo}\n\n{examples}"

    def __len__(self) -> int:
        """
        :return: int, count of examples.
        """
        return len(self.data)

    def __bool__(self) -> bool:
        """
        :return: bool, whether data exist.
        """
        return bool(self.data)

    def __call__(self) -> None:
        """ All the same to request_examples() """
        self.request_examples()

    def __iter__(self) -> iter:
        """
        :return: iter, iterator for data.
        """
        return iter(self.data)

    def __contains__(self,
                     item: Any) -> bool:
        """ Whether the Corpus obj contains the Example obj.

        :param item: obj with the same ex_type.
        :return: whether Corpus obj contains the Example obj.
        :exception TypeError: if wrong type (different Example) given.
        """
        if not isinstance(item, self.ex_type):
            msg = "in supports with the same Example objects"
            logger.error(msg)
            raise TypeError(msg)
        return any(
            item == example
            for example in self.data
        )

    def __getattr__(self,
                    item: str) -> str or int or List or None:
        """ Get request param.

        :param item: item, param name.
        :return: param value or None if it does not exist.
        """
        return self.params.get(item, None)

    def __getitem__(self,
                    item: int or slice) -> Any:
        """ Get example from data or create
        new obj with sliced data.

        :param item: int or slice.
        :return: one example or new obj with the same class and sliced data.
        :exception TypeError: if wrong type given.
        """
        if not isinstance(item, (int, slice)):
            logger.error("Int or slice expected")
            raise TypeError("Int or slice expected")

        if isinstance(item, int):
            return self.data[item]

        new_data = self.data[item]
        new_obj = self.copy()
        new_obj._data = new_data.copy()
        return new_obj

    def __setitem__(self,
                    key: int,
                    value: Any) -> None:
        """ Change the example.

        :param key: int, index of the example.
        :param value: ex_type, new example.
        :return: None.
        :exception TypeError: if wrong type given.
        """
        if not isinstance(value, self.ex_type):
            msg = f"Wrong type {type(value)}, " \
                  f"{type(self.ex_type)} expected"
            logger.error(msg)
            raise TypeError(msg)

        try:
            self._data[key] = value
        except Exception:
            logger.exception(f'Setting item: {value} to {key}')
            raise

    def __delitem__(self,
                    key: int or slice) -> None:
        """ Delete example at the index or
        remove several ones using slice.

        :param key: int or slice, address of item(s) to delete.
        :return: None.
        :exception: if sth went wrong.
        """
        try:
            del self._data[key]
        except Exception:
            logger.exception(f"Deleting item: {key}")
            raise

    def __copy__(self) -> Any:
        """ Copy self.

        :return: copied obj.
        """
        return self[:]


class MainCorpus(Corpus):
    _MODE = 'main'

    def __init__(self, *args, **kwargs):
        # for descendants
        ex_type = kwargs.pop('ex_type', expl.MainExample)
        super().__init__(*args, **kwargs, ex_type=ex_type)
        self._params['mode'] = self._MODE

    def _parse_example(self,
                       example: bs4.element.Tag):
        """ Parse example to Example object.

        :param example: tag, example to parse.
        :return: example obj.
        """
        src = Corpus._get_source(example)
        txt = Corpus._get_text(example)
        txt = txt[:txt.index(src)]
        txt = txt[:txt.rindex('[')].strip()

        doc_url = Corpus._get_doc_url(example)
        ambiguation = Corpus._get_ambiguation(example)
        found_words = Corpus._find_searched_words(example)

        new_ex = self.ex_type(txt, src, ambiguation, found_words, doc_url)
        new_ex.mark_found_words(self.marker)
        return new_ex

    def _parse_doc(self,
                   doc: bs4.element.Tag) -> List[expl.MainExample]:
        """ Parse document to list of examples.

        :param doc: bs4.element.ResultSet,
        """
        if not doc:
            logger.info(f"Empty doc found, params: {self.params}")
            return []
        res = []

        for example in doc.find_all('li'):
            new_ex = self._parse_example(example)
            res += [new_ex]
            self._add_wordforms(new_ex.found_wordforms)
        return res


class NGrams(Corpus):
    # env = sas1_2
    pass


class BiGrams(NGrams):
    pass


class ThreeGrams(NGrams):
    pass


class FourGrams(NGrams):
    pass


class FiveGrams(NGrams):
    pass


class SyntaxCorpus(Corpus):
    pass


class Paper2000Corpus(MainCorpus):
    _MODE = 'paper'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, ex_type=expl.Paper2000Example)
        self._params['mode'] = self._MODE


class PaperRegionalCorpus(MainCorpus):
    _MODE = 'regional'

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, ex_type=expl.PaperRegionalExample)
        self._params['mode'] = self._MODE


class ParallelCorpus(Corpus):
    _MODE = 'para'

    def __init__(self, *args, **kwargs) -> None:
        # for descendants
        ex_type = kwargs.pop('ex_type', expl.ParallelExample)
        super().__init__(*args, **kwargs, ex_type=ex_type)
        self._params['mode'] = self._MODE

    def _parse_text(self,
                    lang: str,
                    text: bs4.element.Tag) -> Any:
        """ Parse one pair element of pair: original – translation.

        :param lang: str, language of text. This param
        :return: Example with one translation of text.
        ParallelExample supports '+=' method.
        """
        src = Corpus._get_source(text)
        ambiguation = Corpus._get_ambiguation(text)
        doc_url = Corpus._get_doc_url(text)
        txt = Corpus._get_text(text)
        # remove source from text
        txt = txt[:txt.index(src)]
        txt = txt[:txt.rindex('[')].strip()

        found_words = Corpus._find_searched_words(text)

        new_txt = self.ex_type(
            {lang: txt}, src, ambiguation, found_words, doc_url)
        new_txt.mark_found_words(self.marker)
        return new_txt

    def _parse_example(self,
                       tag: bs4.element.Tag) -> Any:
        """ Parse a pair: original – translation to Example.

        :param tag: bs4.element.Tag, pair to parse.
        :return: Example.
        """
        # this example's expected to have default args
        result_example = self.ex_type()

        langs = tag.find_all('td', {'class': "para-lang"})
        texts = tag.find_all('li')
        for lang, text in zip(langs, texts):
            lang = lang.text.strip()
            new_txt = self._parse_text(lang, text)
            result_example += new_txt
        return result_example

    def _parse_doc(self,
                   doc: bs4.element.Tag) -> List:
        """ Parse one document.

        :param doc: bs4.element.Tag, document to parse.
        :return: list of Examples.
        """
        res = []
        for example in doc.find_all('table', {'class': 'para'}):
            new_ex = self._parse_example(example)
            res += [new_ex]
            self._add_wordforms(new_ex.found_wordforms)
        return res

    def _load_data(self) -> List:
        """ Load data from csv file.

        :return: list of examples.
        """
        if self.out == 'kwic':
            return super()._load_data()
        with self.file.open('r', encoding='utf-8') as f:
            dm = self._DATA_W_DELIMITER
            qch = self._DATA_W_QUOTCHAR
            reader = csv.reader(f, delimiter=dm, quotechar=qch)

            columns = next(reader)
            end_lang_tags = columns.index('source')
            lang_tags = columns[:end_lang_tags]
            data = []

            for row in reader:
                # to create dict {lang: text in the lang}
                langs = {}
                for num, lang in enumerate(lang_tags):
                    langs[lang] = row[num]

                new_ex = self.ex_type(langs, *row[end_lang_tags:])
                data += [new_ex]

                self._add_wordforms(new_ex.found_wordforms)

        return data


class MultilingualParaCorpus(ParallelCorpus):
    _MODE = 'multi'

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs,
                         ex_type=expl.MultilingualParaExample)
        self._params['mode'] = self._MODE

    def _from_file(self) -> None:
        msg = "Working with files does not support"
        logger.error(msg)
        raise NotImplementedError(msg)

    def dump(self) -> None:
        msg = "Working with files does not support"
        logger.error(msg)
        raise NotImplementedError(msg)


class TutoringCorpus(MainCorpus):
    _MODE = 'school'

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs,
                         ex_type=expl.TutoringExample)
        self._params['mode'] = self._MODE


class DialectalCorpus(MainCorpus):
    _MODE = 'dialect'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs,
                         ex_type=expl.DialectalExample)
        self._params['mode'] = self._MODE


# save lines
class PoeticCorpus(Corpus):
    pass


class SpokenCorpus(MainCorpus):
    _MODE = 'spoken'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs,
                         ex_type=expl.SpokenExample)
        self._params['mode'] = self._MODE


class AccentologicalCorpus(MainCorpus):
    _MODE = 'accent'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs,
                         ex_type=expl.AccentologicalExample)
        self._params['mode'] = self._MODE


class MultimodalCorpus(Corpus):
    MEDIA_FOLDER = Corpus.DATA_FOLDER / 'media'
    _MODE = 'murco'

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, ex_type=expl.MultimodalExample)
        self._params['mode'] = self._MODE

    def _parse_example(self,
                       example: bs4.element.Tag) -> Tuple[str, str, str, list, str]:
        """ Parse example get text, source etc.

        :param example: bs4.element.Tag, example to parse.
        :return: tuple of parsed values.
        """
        src = Corpus._get_source(example)
        txt = Corpus._get_text(example)
        txt = txt[:txt.index(src)]
        txt = txt[:txt.rindex('[')].strip()

        doc_url = Corpus._get_doc_url(example)
        ambiguation = Corpus._get_ambiguation(example)
        found_words = Corpus._find_searched_words(example)

        return txt, src, ambiguation, found_words, doc_url

    def _parse_media(self,
                     media: bs4.element.Tag) -> Tuple[str, str]:
        """ Get link to the media file, filepath.

        :param media: bs4.element.Tag, here they are.
        :return: tuple of str and Path, link and filepath.
        """
        try:
            media_link = media.find('td').a['href']
        except Exception:
            raise
        media_link, filename = media_link.split('?name=')
        return media_link, self.MEDIA_FOLDER / filename

    def _parse_doc(self,
                   doc: bs4.element.Tag) -> List[Any]:
        """ Parse the documents to examples.

        :param doc: doc to parse.
        :return: list of examples.
        """
        try:
            media, example = doc.find_all('td', {'valign': 'top'})
        except ValueError:
            return []
        examples = []

        media_url, filename = self._parse_media(media)
        for example in example.find_all('li'):
            data_from_example = self._parse_example(example)

            new_ex = self.ex_type(*data_from_example, media_url, filename)
            new_ex.mark_found_words(self.marker)
            self._add_wordforms(new_ex.found_wordforms)
            examples += [new_ex]

        return examples

    def download_all(self) -> None:
        """ Download all files.

        :return: None.
        """
        os.makedirs(self.MEDIA_FOLDER, exist_ok=True)

        urls_to_names = [
            (example._media_url, example.filepath)
            for example in self
        ]
        creq.download_docs(urls_to_names)


class MultiPARCCorpus(Corpus):
    pass


class HistoricalCorpus(Corpus):
    pass
