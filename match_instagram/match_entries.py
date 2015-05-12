import logging
import os
import string
import json
from datetime import datetime, date, timedelta
import unicodedata

import pymongo

from instagram.client import InstagramAPI
from instagram.bind import InstagramAPIError

from nltk.corpus import stopwords
from nltk.metrics import edit_distance
from nltk.corpus import wordnet as wn
from gensim import corpora, models, similarities


from mongo_helper import (
    CLIENT,
    DB,
    TRANS_COLLECTION,
    USER_PAIRS_COLLECTION,
    VENMO_INSTAGRAM_MATCHES
)

from instagram_helper import (
    InstagramAPICycler,
    get_all_paginated_data,
    instagram_media_to_dict
)
from insta_query import query

from secrets import TOKENS

log_filename = datetime.now().strftime('%Y%m%d%S_match_entries.log')

RESULT_LOG_LEVEL = 35
logging.addLevelName(RESULT_LOG_LEVEL, 'RESULT')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(log_filename)
fh.setLevel(RESULT_LOG_LEVEL)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)


SLEEP_SECONDS = 60*60
API_CYCLER = InstagramAPICycler(TOKENS)

HEAVY_USER_THRESHOLD = 20

AFTER_CUTOFF_DATE = date(2015, 3, 1)

HOURS_RADIUS = 672

VENMO_DATE_FORMAT_STR = '%Y-%m-%dT%H:%M:%SZ'

STOPLIST = frozenset(stopwords.words('english'))

GRAPHS_PATH = os.path.join(os.getcwd(), 'graphs')
if not os.path.exists(GRAPHS_PATH):
    os.mkdir(GRAPHS_PATH)


def parse_venmo_datetime(datetime_str):
    return datetime.strptime(datetime_str, VENMO_DATE_FORMAT_STR)


def get_venmo_trans_datetimes(transactions):
    return [parse_venmo_datetime( t.get('created_time') ) for t in transactions]

def get_instagram_datetimes(media):
    return [m.created_time for m in media]


def venmo_user_trans(user_id):
    pipeline = [
        {"$unwind": "$transactions"},
        {"$match": {"$or": [
            {"actor.id": user_id},
            {"transactions.target.id": user_id}
        ]}},
        {"$sort": {"created_time": 1}}
    ]

    return [r for r in TRANS_COLLECTION.aggregate(pipeline)]


def get_instagram_api_data(instagram_user):
    instagram_id = instagram_user.get('id')
    media = get_all_paginated_data(API_CYCLER.api, 'user_recent_media', user_id=instagram_id, count=100)
    logger.log(RESULT_LOG_LEVEL, '%d Media fetched for Instagram user %s (%s)' % (len(media), instagram_user.get('username'), instagram_user.get('id')))
    return media


def get_venmo_api_data(venmo_user):
    venmo_id = venmo_user.get('id')
    venmo_trans = venmo_user_trans(venmo_id)
    logger.log(RESULT_LOG_LEVEL, '%d Transactions fetched for Venmo user %s (%s)' % (len(venmo_trans), venmo_user.get('username'), venmo_user.get('id')))
    return venmo_trans


def get_api_data(venmo_user, instagram_user):
    media = get_instagram_api_data(instagram_user)
    venmo_trans = get_venmo_api_data(venmo_user)
    return venmo_trans, media


def instagram_caption_words(instagram_media):
    raw_captions = [getattr(post.caption, 'text') for post in instagram_media if hasattr(post.caption, 'text')]
    return get_word_dictionary(raw_captions)


def venmo_message_words(venmo_messages):
    venmo_messages_raw = [tran.get('message') for tran in sample_trans]
    return get_word_dictionary(venmo_messages_raw)


def filter_ascii_punctuation(word):
    return ''.join([c for c in word if c not in string.punctuation])


def get_words(document):
    return [
        filter_ascii_punctuation(word) for
        word in document.lower().replace('#', '').split() if word not in STOPLIST
   ]

def get_word_dictionary(documents):
    return [get_words(document) for document in documents]



tfidf_threshold = 0.65
sim_match_index = 0
sim_match_words = 1

def text_matches(venmo_trans, instagram_media):
    instagram_words = instagram_caption_words(instagram_media)
    i_word_dict, tfidf_model, tfidf_index = build_tfidf_model(instagram_words)

#     doc = 'test sushi with pals'
    for i, msg in enumerate([tran.get('message') for tran in venmo_trans]):
#         vec_bow = i_word_dict.doc2bow(msg.lower().split())
        vec_bow = i_word_dict.doc2bow(get_words(msg))
        vec_tfidf = tfidf_model[vec_bow]
        sims = tfidf_index[vec_tfidf]
        tfidf_sims_list = [sim for sim in list(enumerate(sims)) if sim[sim_match_words] > tfidf_threshold]
#         report_results(tfidf_sims_list, instagram_words)
        if tfidf_sims_list:
#             print 'FOUND MATCHES FOR VENMO MSG %s' % msg
            yield venmo_trans[i], [instagram_media[match[sim_match_index]] for match in tfidf_sims_list]
        else:
            yield None, None


def build_tfidf_model(instagram_words):
    i_word_dict = corpora.Dictionary(instagram_words)
    i_corpus = [i_word_dict.doc2bow(word) for word in instagram_words]
    tfidf_model = models.TfidfModel(i_corpus)
    corpus_tfidf = tfidf_model[i_corpus]
    tfidf_index = similarities.MatrixSimilarity(tfidf_model[corpus_tfidf])
    return i_word_dict, tfidf_model, tfidf_index


def report_results(sims, media_captions):
    for i, sim in enumerate(sims):
        if sim[1] > 0:
            logger.log(RESULT_LOG_LEVEL, '%s -- %s' % (sim, media_captions[i]))


diff_after = timedelta(hours=-HOURS_RADIUS)
diff_before = timedelta(hours=HOURS_RADIUS)

def media_near_transaction(tran, media):
    tran_datetime = parse_venmo_datetime( tran.get('created_time') )
    after_datetime = tran_datetime + diff_after
    before_datetime = tran_datetime + diff_before
    return [
        m for m in media if
        m.created_time > after_datetime and
        m.created_time < before_datetime
    ]


def venmo_instagram_matches(venmo_trans, instagram_media):
    text_iter = text_matches(venmo_trans, instagram_media)
    while True:
        try:
            venmo_tran, instagram_caption_matches = next(text_iter)
            if venmo_tran is not None:
                instagram_nearby_date = media_near_transaction(venmo_tran, instagram_media)
                vi_match = set(instagram_nearby_date).intersection(instagram_caption_matches)
                if vi_match:
                    yield venmo_tran, list(vi_match)
                else:
                    continue
        except ValueError as e:
            logger.debug(e)
            continue
        except StopIteration:
            break
        # for venmo_tran, instagram_caption_matches in text_matches(venmo_trans, instagram_media):
    #         if venmo_tran:
    # #             print venmo_tran.get('message'), [getattr(post.caption, 'text') for post in instagram_caption_matches]
    #             instagram_nearby_date = media_near_transaction(venmo_tran, instagram_media)
    #             vi_match = set(instagram_nearby_date).intersection(instagram_caption_matches)
    #             if vi_match:
    #                 yield venmo_tran, list(vi_match)
    #             else:
    #                 continue
    # except ValueError as e:
    #     logger.debug(e)
    # except StopIteration as e:
    #     break


def instagram_json(media):
    json.dumps(media.__dict__, sort_keys=True, indent=4)


def main(tokens, user_threshold, repopulate=False, rematch=False):
    if rematch:
        query(tokens, user_threshold, repopulate=repopulate)

    user_matches = [result for result in VENMO_INSTAGRAM_MATCHES.find()]
    logger.log(RESULT_LOG_LEVEL, 'Total Venmo-Instagram user matches: %d' % len(user_matches))

    update_matches = []
    errors = []
    for i, user_pair in enumerate(user_matches):
        instagram_user = user_pair.get('instagram')
        venmo_user = user_pair.get('venmo')
        try:
            venmo_trans, instagram_media = get_api_data(venmo_user, instagram_user)
            logger.log(RESULT_LOG_LEVEL, 'Checking for matching Venmo and Instragram updates for user %s/%s' % (venmo_user.get('username'), instagram_user.get('username')))
            update_matches = []
            if venmo_trans and instagram_media:
                for va, ia in venmo_instagram_matches(venmo_trans, instagram_media):
                    logger.log(RESULT_LOG_LEVEL, 'SUCCESSFUL MATCH')
                    logger.log(RESULT_LOG_LEVEL, '\tVENMO:\t%s' % va)
                    try:
                        logger.log(RESULT_LOG_LEVEL, '\tINSTAGRAM:\t%s' % instagram_json(ia))
                    except TypeError as e:
                        logger.log(RESULT_LOG_LEVEL, e)
                        for i in ia:
                            logger.log(RESULT_LOG_LEVEL, '\tINSTAGRAM:\t%s' % instagram_json(ia))
                    update_matches.append((va, ia))
                else:
                    continue
        except InstagramAPIError as e:
            if e.status_code == 400:
                logger.debug("ERROR: Instagram user %s -- %s is set to private." % (instagram_user.get('username'), instagram_user.get('id')))
            continue


if __name__ == '__main__':
    main(TOKENS, HEAVY_USER_THRESHOLD)