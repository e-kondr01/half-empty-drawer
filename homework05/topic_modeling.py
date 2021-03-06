import config
import copy
import gensim
import pandas as pd
import pyLDAvis
import pyLDAvis.gensim
import pymorphy2
import requests
import time

from gensim.corpora.dictionary import Dictionary
from gensim.models.ldamulticore import LdaModel
from nltk.corpus import stopwords
from typing import List, Dict

morph = pymorphy2.MorphAnalyzer()
access_token = config.VK_CONFIG['access_token']

stop_words_default = stopwords.words('russian')
stop_words_default_en = stopwords.words('english')
additional_stop_words = ['который', 'также', 'это', 'свой', 'весь', "самый",
                         'наш', "мочь"]
stop_words = stop_words_default + additional_stop_words + stop_words_default_en


def get_wall(
    owner_id: str = '',
    domain: str = '',
    offset: int = 0,
    count: int = 10,
    filter: str = 'owner',
    extended: int = 0,
    fields: str = '',
    v: str = '5.103'
) -> List[Dict]:
    """
    Возвращает список записей со стены пользователя или сообщества.

    @see: https://vk.com/dev/wall.get

    :param owner_id: Идентификатор пользователя или сообщества, со стены
     которого необходимо получить записи.
    :param domain: Короткий адрес пользователя или сообщества.
    :param offset: Смещение, необходимое для выборки определенного
     подмножества записей.
    :param count: Количество записей, которое необходимо получить (0 - все
     записи).
    :param filter: Определяет, какие типы записей на стене необходимо получить.
    :param extended: 1 — в ответе будут возвращены дополнительные поля
     profiles и groups, содержащие информацию о пользователях и сообществах.
    :param fields: Список дополнительных полей для профилей и сообществ,
     которые необходимо вернуть.
    :param v: Версия API.
    """
    wall = []

    c = 0
    start_time = time.time()
    curr_time = time.time()
    for _ in range(count // 2500 + 1):
        # Time-out для запросов (не больше 3 в секунду)
        prev_time = curr_time
        curr_time = time.time()
        if 1 - (curr_time - start_time) <= 0:
            start_time = prev_time
        elif c == 3:
            wait = 1 - (curr_time - start_time)
            time.sleep(wait)
            c = 1
            start_time = time.time()
        else:
            c += 1

        curr_count = 2500 if count > 2500 else count
        n_queries = curr_count // 100
        code = 'return ['
        for i in range(n_queries):
            query = {
                'owner_id': owner_id,
                'domain': domain,
                'offset': offset + i * 100,
                'count': 100,
                'filter': filter,
                'extended': extended,
                'fields': fields,
                'v': v
            }

            code += f'API.wall.get({str(query)})'
            if i < n_queries - 1:
                code += ', '
            else:
                code += '];'

        response = requests.post(
            url="https://api.vk.com/method/execute",
            data={
                "code": code,
                "access_token": access_token,
                "v": v
            }
        )
        for i in range(n_queries):
            wall.extend(response.json()['response'][i]['items'])

        count -= 2500
        if count <= 0:
            break
        offset += 2500

    return wall


def prep_text(wall: List[Dict], count: int) -> List:
    """ Подготовка текста к построению тематической модели """
    text = ''
    for i in range(count):
        try:
            text += wall[i]['text']
            text += ' '
        except IndexError:
            break

    # Удаление ссылок и  хэштегов
    textlist = text.split()
    newtextlist = copy.copy(textlist)
    for w in textlist:
        if 'https://' in w or '#' in w:
            newtextlist.remove(w)
    text = ' '.join(newtextlist)

    # Удаление символов, не являющихся буквами (пунктуация, эмодзи и т.д.)
    newtext = ''
    for c in text:
        if c.isalpha() is True or c == ' ':
            newtext += c
        if c == '\n':
            newtext += ' '

    # Проведение нормализации
    textlist = newtext.split()
    for i in range(len(textlist)):
        textlist[i] = morph.parse(textlist[i])[0].normal_form

    # Удаление стоп-слов
    newtextlist = copy.copy(textlist)
    for w in textlist:
        if w in stop_words or len(w) == 1:
            newtextlist.remove(w)

    return newtextlist


def topic_model_visualize(textlist: list, num_topics: int) -> None:
    """Визуализация тематической модели"""
    textlist = [textlist]
    common_dictionary = Dictionary(textlist)
    common_corpus = [common_dictionary.doc2bow(text) for text in textlist]
    lda = LdaModel(common_corpus, num_topics=num_topics)

    vis = pyLDAvis.gensim.prepare(lda, common_corpus, common_dictionary)
    pyLDAvis.save_html(vis, 'LDA.html')
    pyLDAvis.show(data=vis, open_browser=True)


if __name__ == '__main__':
    wall1 = get_wall(domain='itmoru', count=3000)
    wall2 = get_wall(domain='lentach', count=3000)
    wall3 = get_wall(domain='dotatoday', count=3000)
    text1 = prep_text(wall1, 3000)
    text2 = prep_text(wall2, 3000)
    text3 = prep_text(wall3, 3000)
    textlist1 = text1 + text2 + text3
    topic_model_visualize(textlist1, 3)
