import os
from pathlib import Path
from time import sleep

import pytest

import rnc.corpora as rnc


class TemplateCorpusTest:
    corp_type = rnc.Corpus

    corp_normal_obj = None
    corp_kwic_obj = None

    full_query = {
        'ты': {
            'gramm': {
                'case': ['acc', 'nom', 'gen'],
                'num': ['sg', 'pl']
            },
            'flags': {
                'position': ['amark', 'bmark'],
            }
        }
    }

    #########################
    #    Test requesting    #
    #########################

    def test_empty_query(self):
        with pytest.raises(ValueError):
            self.corp_type('', 1, marker=str.upper)

    def test_p_count_zero(self):
        with pytest.raises(ValueError):
            self.corp_type('корпус', 0, marker=None)

    def test_one_str_with_one_word(self):
        corp = self.corp_type('ты', 1, marker=str.capitalize, spd=1, dpp=5)
        corp.request_examples()

        assert len(corp) > 1
        sleep(5)

    def test_one_form_without_gram(self):
        corp = self.corp_type({'ты': ''}, 1, marker=str.capitalize, spd=1, dpp=5)
        corp.request_examples()

        assert len(corp) > 1
        sleep(5)

    def test_one_form_with_one_gram(self):
        corp = self.corp_type({'ты': 'nom'}, 1, marker=str.capitalize, spd=1)
        corp.request_examples()

        assert len(corp) > 1
        sleep(5)

    def test_one_form_with_grams_and_flags(self):
        query = {
            'ты': {
                'gramm': 'acc',
                'flags': 'amark'
            }
        }
        corp = self.corp_type(query, 1, marker=str.capitalize)
        corp.request_examples()

        assert len(corp) > 1
        sleep(5)

    def test_one_form_with_several_grams_and_flags(self):
        corp = self.corp_type(self.full_query, 1, marker=str.capitalize)
        corp.request_examples()

        assert len(corp) > 1
        sleep(5)

    def test_full_query_with_lexform(self):
        corp = self.corp_type('слово бога', 1, text='lexform')
        corp.request_examples()

        assert len(corp) > 1
        sleep(5)

    def test_full_query_with_kwic_without_kwsz(self):
        corp = self.corp_type(self.full_query, 1, marker=str.capitalize, out='kwic')
        corp.request_examples()

        assert len(corp) > 1
        sleep(5)

    def test_full_query_with_kwic_with_kwsz(self):
        corp = self.corp_type(self.full_query, 1, marker=str.capitalize, out='kwic', kwsz=7)
        corp.request_examples()

        assert len(corp) > 1
        sleep(5)

    def test_sort_in_request(self):
        default = self.corp_type('ты', 1)
        default.request_examples()
        sleep(5)

        by_creation_date = self.corp_type('ты', 1, sort='i_grcreated_inv')
        by_creation_date.request_examples()
        sleep(5)

        assert default.data != by_creation_date.data

    def test_subcorpus(self):
        corp = self.corp_type(
            'ты', 1,
            subcorpus="JSONeyJkb2Nfc2V4IjogWyLQvNGD0LYiXSwgImRvY19pX3RhZ2dpbmciOiBbIjEiXX0%3D"
        )
        corp.request_examples()

        assert len(corp) >= 1
        sleep(5)

    def test_call(self):
        corp = self.corp_type('ты', 1, marker=str.capitalize, out='kwic')
        corp()

        assert len(corp) > 1

    #########################
    #   Working with file   #
    #########################

    def test_dump_normal(self):
        self.corp_normal_obj.dump()

    def test_dump_kwic(self):
        self.corp_kwic_obj.dump()

    def test_load_normal(self):
        corp = self.corp_type(file=self.corp_normal_obj.file)

        assert len(corp) == len(self.corp_normal_obj)
        assert (
            from_file == from_corp
            for from_file, from_corp in zip(corp, self.corp_normal_obj)
        )

    def test_load_kwic(self):
        corp = self.corp_type(file=self.corp_kwic_obj.file)

        assert len(corp) == len(self.corp_kwic_obj)
        assert (
            from_file == from_corp
            for from_file, from_corp in zip(corp, self.corp_kwic_obj)
        )

    def test_load_to_wrong_corpus(self):
        with pytest.raises(NotImplementedError):
            self.corp_type(file='data\\wrong_mode.csv')

    def test_request_if_base_loaded(self):
        corp = self.corp_type(file=self.corp_normal_obj.file)
        with pytest.raises(RuntimeError):
            corp.request_examples()

    def test_wrong_filetype(self):
        with pytest.raises(TypeError):
            corp = self.corp_type('ты', 1, file='file.txt')

    def test_default_filetype(self):
        corp = self.corp_type('ты', 1)

        assert isinstance(corp.file, Path) and corp.file.suffix == '.csv'

    def test_equality_wordforms_from_rnc_and_from_file(self):
        corp = self.corp_type(file=self.corp_kwic_obj.file)

        assert all(
            from_file == from_corp
            for from_file, from_corp in zip(corp, self.corp_kwic_obj)
        )

    #########################
    #    Test properties    #
    #########################

    def test_data_type(self):
        assert isinstance(self.corp_normal_obj.data, list)

    def test_data_elements_type(self):
        assert all(
            isinstance(ex, self.corp_normal_obj.ex_type)
            for ex in self.corp_normal_obj
        )

    def test_query_dict(self):
        corp = self.corp_type({'ты': 'acc'}, 1)

        assert isinstance(corp.query, dict) and corp.query

    def test_query_str(self):
        corp = self.corp_type('ты', 1)

        assert isinstance(corp.query, str) and corp.query

    def test_forms_in_query_dict(self):
        corp = self.corp_type({'ты': 'acc', 'готов': {}}, 1)

        assert isinstance(corp.forms_in_query, list)
        assert all(isinstance(form, str) for form in corp.forms_in_query)
        assert len(corp.forms_in_query) is 2
        assert corp.forms_in_query == ['ты', 'готов']

    def test_forms_in_query_str(self):
        corp = self.corp_type('ты готов ', 1)

        assert isinstance(corp.forms_in_query, list)
        assert all(isinstance(form, str) for form in corp.forms_in_query)
        assert len(corp.forms_in_query) is 2
        assert corp.forms_in_query == ['ты', 'готов']

    def test_p_count(self):
        corp = self.corp_type('ты', 1)

        assert corp.p_count is 1

    def test_found_wordforms_from_file(self):
        corp = self.corp_type(file=self.corp_normal_obj.file)

        assert corp.found_wordforms == self.corp_normal_obj.found_wordforms

    def test_url(self):
        corp = self.corp_type('ты', 1)

        assert isinstance(corp.url, str) and corp.url

    def test_amount_of_docs_normal(self):
        assert isinstance(self.corp_normal_obj.amount_of_docs, int)

    def test_amount_of_docs_kwic(self):
        assert self.corp_kwic_obj.amount_of_docs is None

    def test_amount_of_contexts_normal(self):
        assert isinstance(self.corp_normal_obj.amount_of_contexts, int)

    def test_amount_of_contexts_kwic(self):
        assert isinstance(self.corp_kwic_obj.amount_of_contexts, int)

    ##########################
    # Test working with data #
    ##########################

    def test_open_url(self):
        self.corp_normal_obj.open_url()

    def test_open_graphic(self):
        self.corp_normal_obj.open_graphic()

    def test_copy(self):
        copy = self.corp_normal_obj.copy()

        assert copy.data == self.corp_normal_obj.data

    def test_sort_data(self):
        copy = self.corp_normal_obj.copy()
        copy.sort_data(key=lambda x: len(x.txt))

        assert copy.data != self.corp_normal_obj.data

    def test_pop(self):
        copy = self.corp_normal_obj.copy()
        example = copy.pop(0)

        assert any(
            example == ex
            for ex in self.corp_normal_obj)
        assert all(
            example != ex
            for ex in copy
        )

    def test_contains(self):
        copy = self.corp_normal_obj.copy()
        example = copy.pop(0)

        assert (example in self.corp_normal_obj and
                example not in copy)

    def test_shuffle(self):
        copy = self.corp_normal_obj.copy()
        copy.shuffle()

        assert copy.data != self.corp_normal_obj.data

    def test_clear(self):
        copy = self.corp_normal_obj.copy()
        copy.clear()

        assert not copy.data
        assert copy.query
        assert copy.p_count
        assert copy.params

    def test_filter(self):
        copy = self.corp_normal_obj.copy()
        copy.filter(lambda x: x.txt is None)

        assert len(copy) == 0

    def test_getattr_normal(self):
        mode = self.corp_normal_obj.mode

        assert isinstance(mode, str) and mode

    def test_getattr_none(self):
        assert self.corp_normal_obj.name is None

    def test_getitem_one(self):
        item = self.corp_normal_obj[0]

        assert item in self.corp_normal_obj

    def test_getitem_slice(self):
        sliced = self.corp_normal_obj[::-1]

        assert all(
            lhs == rhs
            for lhs, rhs in zip(self.corp_normal_obj.data[::-1], sliced)
        )

    def test_delitem(self):
        copy = self.corp_normal_obj.copy()
        del copy[:]

        assert copy == 0

    ##########################
    #        Test <=>        #
    ##########################

    def test_lt_with_int(self):
        assert self.corp_normal_obj < 10
        assert self.corp_kwic_obj < 10

    def test_lt_with_corp(self):
        copy = self.corp_normal_obj.copy()
        del copy[0]

        assert copy < self.corp_normal_obj

    def test_le_with_int(self):
        assert self.corp_normal_obj <= 5
        assert self.corp_kwic_obj <= 5

    def test_le_with_corp(self):
        copy = self.corp_normal_obj.copy()
        del copy[0]

        assert copy <= self.corp_normal_obj

    def test_eq_with_int(self):
        assert self.corp_normal_obj == len(self.corp_normal_obj)
        assert self.corp_kwic_obj == len(self.corp_kwic_obj)

    def test_eq_with_corp(self):
        copy = self.corp_normal_obj.copy()

        assert copy == self.corp_normal_obj

    def test_ne_with_int(self):
        assert self.corp_normal_obj != 0
        assert self.corp_kwic_obj != 0

    def test_ne_with_corp(self):
        copy = self.corp_normal_obj.copy()
        del copy[0]

        assert copy != self.corp_normal_obj

    def test_gt_with_int(self):
        assert self.corp_normal_obj > 0
        assert self.corp_kwic_obj > 0

    def test_gt_with_corp(self):
        copy = self.corp_normal_obj.copy()
        del copy[0]

        assert self.corp_normal_obj > copy

    def test_ge_with_int(self):
        assert self.corp_normal_obj >= 1
        assert self.corp_kwic_obj >= 1

    def test_ge_with_corp(self):
        copy = self.corp_normal_obj.copy()
        del copy[0]

        assert self.corp_normal_obj >= copy

    ##########################
    #   Test class setters   #
    ##########################

    def test_set_spd_normal(self):
        self.corp_type.set_spd(20)
        corp = self.corp_type('ты', 1)

        assert corp.spd is 20

    def test_set_spd_exception(self):
        with pytest.raises(TypeError):
            self.corp_type.set_spd('12')

    def test_set_dpp_normal(self):
        self.corp_type.set_dpp(20)
        corp = self.corp_type('ты', 1)

        assert corp.dpp is 20

    def test_set_dpp_exception(self):
        with pytest.raises(TypeError):
            self.corp_type.set_dpp('12')

    def test_set_text_normal(self):
        self.corp_type.set_text('lexform')
        corp = self.corp_type('ты', 1)

        assert corp.text == 'lexform'

    def test_set_text_exception(self):
        with pytest.raises(TypeError):
            self.corp_type.set_text(12)

    def test_set_sort_normal(self):
        self.corp_type.set_sort('i_grcreated_inv')
        corp = self.corp_type('ты', 1)

        assert corp.sort == 'i_grcreated_inv'

    def test_set_sort_exception(self):
        with pytest.raises(TypeError):
            self.corp_type.set_sort(12)

    def test_set_min_normal(self):
        self.corp_type.set_min(10)
        corp = self.corp_type('ты готов', 1)

        assert corp.min2 is 10

    def test_set_min_exception(self):
        with pytest.raises(TypeError):
            self.corp_type.set_min('12')

    def test_set_max_normal(self):
        self.corp_type.set_max(10)
        corp = self.corp_type('ты готов', 1)

        assert corp.max2 is 10

    def test_set_max_exception(self):
        with pytest.raises(TypeError):
            self.corp_type.set_max('12')

    def test_set_restrict_show_exception_str(self):
        with pytest.raises(TypeError):
            self.corp_type.set_restrict_show('False')

    def test_set_restrict_show_exception_list(self):
        with pytest.raises(TypeError):
            self.corp_type.set_restrict_show([False])


class TestMainCorpus(TemplateCorpusTest):
    corp_type = rnc.MainCorpus

    # for test working with file
    corp_normal_obj = corp_type('ты', 1, dpp=5, spd=1)
    corp_kwic_obj = corp_type('ты', 1, dpp=5, spd=1, out='kwic')

    corp_normal_obj.request_examples()
    sleep(5)
    corp_kwic_obj.request_examples()
    sleep(5)


class TestPaper2000Corpus(TemplateCorpusTest):
    corp_type = rnc.Paper2000Corpus

    corp_normal_obj = corp_type('ты', 1, dpp=5, spd=1)
    corp_kwic_obj = corp_type('ты', 1, dpp=5, spd=1, out='kwic')

    corp_normal_obj.request_examples()
    sleep(5)
    corp_kwic_obj.request_examples()
    sleep(5)

    def test_subcorpus(self):
        corp = self.corp_type(
            'ты', 1,
            subcorpus="JSONeyJkb2NfaV9sZV9zdGFydF95ZWFyIjogWyIyMDEwIl19"
        )
        corp.request_examples()

        assert len(corp) >= 1
        sleep(5)


class TestPaperRegionalCorpus(TemplateCorpusTest):
    corp_type = rnc.PaperRegionalCorpus

    corp_normal_obj = corp_type('ты', 1, dpp=5, spd=1)
    corp_kwic_obj = corp_type('ты', 1, dpp=5, spd=1, out='kwic')

    corp_normal_obj.request_examples()
    sleep(5)
    corp_kwic_obj.request_examples()
    sleep(5)

    def test_full_query_with_lexform(self):
        corp = self.corp_type('Владимир Путин', 1, text='lexform')
        corp.request_examples()

        assert len(corp) > 1
        sleep(5)

    def test_subcorpus(self):
        corp = self.corp_type(
            'ты', 1,
            subcorpus="JSONeyJkb2NfaV9sZV9zdGFydF95ZWFyIjogWyIyMDEwIl19"
        )
        corp.request_examples()

        assert len(corp) >= 1
        sleep(5)

    def test_open_graphic(self):
        with pytest.raises(RuntimeError):
            self.corp_normal_obj.open_graphic()


class TestParallelCorpus(TemplateCorpusTest):
    corp_type = rnc.ParallelCorpus

    corp_normal_obj = corp_type('ты', 1, dpp=5, spd=1)
    corp_kwic_obj = corp_type('ты', 1, dpp=5, spd=1, out='kwic')

    corp_normal_obj.request_examples()
    sleep(5)
    corp_kwic_obj.request_examples()
    sleep(5)

    def test_full_query_with_lexform(self):
        corp = self.corp_type('Владимир Путин', 1, text='lexform')
        corp.request_examples()

        assert len(corp) > 1
        sleep(5)

    def test_subcorpus(self):
        corp = self.corp_type(
            'ты', 1,
            subcorpus='JSONeyJkb2NfaV9sZV9zdGFydF95ZWFyIjogWyIyMDAwIl19'
        )
        corp.request_examples()

        assert len(corp) >= 1
        sleep(5)

    def test_sort_data(self):
        copy = self.corp_normal_obj.copy()
        copy.sort_data(key=lambda x: len(x.ru))

        assert copy.data != self.corp_normal_obj.data

    def test_open_graphic(self):
        with pytest.raises(RuntimeError):
            self.corp_normal_obj.open_graphic()


class TestMultilingualParaCorpus(TemplateCorpusTest):
    corp_type = rnc.MultilingualParaCorpus

    corp_normal_obj = corp_type('ты', 1, dpp=5, spd=1)
    corp_kwic_obj = corp_type('ты', 1, dpp=5, spd=1, out='kwic')

    corp_normal_obj.request_examples()
    sleep(5)
    corp_kwic_obj.request_examples()
    sleep(5)

    def test_full_query_with_lexform(self):
        corp = self.corp_type('ты готов', 1, text='lexform')
        corp.request_examples()

        assert len(corp) > 1
        sleep(5)

    def test_subcorpus(self):
        pass
        # it's impossible to set subcorpus in MultilingualParaCorpus

        # corp = self.corp_type(
        #     'ты', 1,
        #     subcorpus='JSONeyJkb2NfaV9sZV9zdGFydF95ZWFyIjogWyIyMDAwIl19'
        # )
        # corp.request_examples()
        #
        # assert len(corp) >= 1
        # sleep(5)

    def test_sort_data(self):
        copy = self.corp_normal_obj.copy()
        copy.sort_data(key=lambda x: len(x.src))

        assert copy.data != self.corp_normal_obj.data

    def test_dump_normal(self):
        with pytest.raises(NotImplementedError):
            super().test_dump_normal()

    def test_dump_kwic(self):
        with pytest.raises(NotImplementedError):
            super().test_dump_kwic()

    def test_load_kwic(self):
        pass

    def test_load_normal(self):
        pass

    def test_load_to_wrong_corpus(self):
        pass

    def test_request_if_base_loaded(self):
        pass

    def test_equality_wordforms_from_rnc_and_from_file(self):
        pass

    def test_found_wordforms_from_file(self):
        pass

    def test_open_graphic(self):
        with pytest.raises(RuntimeError):
            self.corp_normal_obj.open_graphic()


class TestTutoringCorpus(TemplateCorpusTest):
    corp_type = rnc.TutoringCorpus

    corp_normal_obj = corp_type('ты', 1, dpp=5, spd=1)
    corp_kwic_obj = corp_type('ты', 1, dpp=5, spd=1, out='kwic')

    corp_normal_obj.request_examples()
    sleep(5)
    corp_kwic_obj.request_examples()
    sleep(5)

    def test_full_query_with_lexform(self):
        corp = self.corp_type('Владимир Путин', 1, text='lexform')
        corp.request_examples()

        assert len(corp) >= 1
        sleep(5)

    def test_open_graphic(self):
        with pytest.raises(RuntimeError):
            self.corp_normal_obj.open_graphic()


class TestDialectalCorpus(TemplateCorpusTest):
    corp_type = rnc.DialectalCorpus

    corp_normal_obj = corp_type('ты', 1, dpp=5, spd=1)
    corp_kwic_obj = corp_type('ты', 1, dpp=5, spd=1, out='kwic')

    corp_normal_obj.request_examples()
    sleep(5)
    corp_kwic_obj.request_examples()
    sleep(5)

    def test_full_query_with_lexform(self):
        corp = self.corp_type('дак ты', 1, text='lexform')
        corp.request_examples()

        assert len(corp) > 1
        sleep(5)

    def test_subcorpus(self):
        corp = self.corp_type(
            'ты', 1,
            subcorpus='JSONeyJkb2NfcmVnaW9uIjogWyLQmtCw0YDQtdC70LjRjyJdfQ%3D%3D'
        )
        corp.request_examples()

        assert len(corp) >= 1
        sleep(5)

    def test_open_graphic(self):
        with pytest.raises(RuntimeError):
            self.corp_normal_obj.open_graphic()


class TestSpokenCorpus(TemplateCorpusTest):
    corp_type = rnc.SpokenCorpus

    corp_normal_obj = corp_type('ты', 1, dpp=5, spd=1)
    corp_kwic_obj = corp_type('ты', 1, dpp=5, spd=1, out='kwic')

    corp_normal_obj.request_examples()
    sleep(5)
    corp_kwic_obj.request_examples()
    sleep(5)

    def test_open_graphic(self):
        with pytest.raises(RuntimeError):
            self.corp_normal_obj.open_graphic()


class TestAccentologicalCorpus(TemplateCorpusTest):
    corp_type = rnc.AccentologicalCorpus

    corp_normal_obj = corp_type('ты', 1, dpp=5, spd=1)
    corp_kwic_obj = corp_type('ты', 1, dpp=5, spd=1, out='kwic')

    corp_normal_obj.request_examples()
    sleep(5)
    corp_kwic_obj.request_examples()
    sleep(5)

    def test_subcorpus(self):
        corp = self.corp_type(
            'ты', 1,
            subcorpus='JSONeyJkb2NfYXV0aG9yIjogWyLQkC7QoS4g0J_Rg9GI0LrQuNC9Il0sICJkb2NfaV9sZV9lbmRfeWVhciI6IFsiMTgzMCJdfQ%3D%3D'
        )
        corp.request_examples()

        assert len(corp) >= 1
        sleep(5)

    def test_open_graphic(self):
        with pytest.raises(RuntimeError):
            self.corp_normal_obj.open_graphic()


class TestMultimodalCorpus(TemplateCorpusTest):
    corp_type = rnc.MultimodalCorpus

    corp_normal_obj = corp_type('корпус', 1, dpp=5, spd=1)
    corp_kwic_obj = corp_type('корпус', 1, dpp=5, spd=1, out='kwic')

    corp_normal_obj.request_examples()
    sleep(5)
    corp_kwic_obj.request_examples()
    sleep(5)

    def test_download_all(self):
        self.corp_normal_obj.download_all()
        files = os.listdir(self.corp_normal_obj.MEDIA_FOLDER)

        assert all(
            ex.filepath.name in files
            for ex in self.corp_normal_obj
        )