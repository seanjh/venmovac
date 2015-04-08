import sys
import time
import argparse
# from math import *

from instagram.client import InstagramAPI
from instagram.bind import InstagramAPIError
import pymongo

parser = argparse.ArgumentParser()
parser.add_argument('tokens', nargs='*')
args = parser.parse_args()

access_tokens = []
access_token = None
if args.tokens:
    access_tokens = args.tokens
    access_token = access_tokens[-1]
else:
    access_token = ""


class InstagramAPICycler(object):
    def __init__(self, tokens):
        self._tokens = tokens
        self._apis = {}
        for i, token in enumerate(tokens):
            self._apis[i] = {
                "api_object": InstagramAPI(access_token=access_token),
                "access_token": token,
                "usage_count": 0
            }
        self._pos = 0

    @property
    def api(self):
        the_api = self._apis[self._pos]
        the_api["usage_count"] += 1
        print 'Using api token %s (%d uses)' % (
                the_api.get('access_token'),
                the_api.get('usage_count')
            )
        self._pos = (self._pos + 1) % len(self._tokens)
        return the_api.get('api_object')


# api = InstagramAPI(access_token=access_token)

if access_tokens:
    api_cycler = InstagramAPICycler(access_tokens)
else:
    api_cycler = InstagramAPICycler([access_token])

CLIENT = pymongo.MongoClient('localhost', 27017)
DB = CLIENT['venmo']
trans_collection = DB['trans']
user_pairs_collection = DB['user_pairs']
venmousers = DB['venmo_users']
venmousers.create_index("venmo_id")
venmo_user_ids = set()


def match_venmo_instagram(user_pairs):
    for result in user_pairs:
        user = result.get('_id')
        targets = result.get('targets')
        get_one_instagram_user(user, targets)


def populate_user_pairs_collection(trans_collection):
    print "BEGINNING populate_user_pairs_collection"
    pipeline = [
        {"$match": {"actor.external_id": { "$exists": True }}},
        {"$match": {"transactions.0.target.external_id": {"$exists": True}}},
        {"$unwind": "$transactions"},
        {"$group": {
            "_id": "$actor",
            "targets": {"$addToSet": "$transactions.target"}
        }},
        {"$out": "user_pairs"}
    ]

    result = trans_collection.aggregate(pipeline, allowDiskUse=True)
    print result
    print "DONE populate_user_pairs_collection"


def get_networked_users(trans_collection, limit=20, populate=True):
    if populate:
        populate_user_pairs_collection(trans_collection)

    print "BEGINNING get_networked_users"

    # Finds matches using an array index, so value to match is limit-1
    targets_index_str = "targets.%d" % (limit - 1)
    print "targets_index_str: %s" % targets_index_str

    pipeline = [
        {"$match": {targets_index_str: {"$exists": True }}},
        {"$unwind": "$targets"},
        {"$group": {
            "_id": "$_id",
            "total_targets": {"$sum": 1}
        }},
        {"$sort": {"total_targets": -1}}
    ]
    cursor = user_pairs_collection.aggregate(pipeline)

    heavy_users = []
    for result in cursor:
        # print result
        if result.get('_id') and result['_id'].get('username'):
            pairs = get_pairs_for_user(result.get('_id'))
            print '%s Targets: %d' % (
                result['_id'].get('username'),
                len(pairs.get('targets')) if pairs.get('targets') else -1
            )
            heavy_users.append(pairs)

    return heavy_users


def get_pairs_for_user(user):
    username = user.get('username')
    external_id = user.get('external_id')
    results = [r for r in user_pairs_collection.find(
        {"_id.external_id": external_id}
    )]
    if results:
        return results[0]
    return None
    # return user_pairs_collection.find({
    #         "_id.username": username
    #     })


def instagram_user_string(instagram_user):
    return "fullname: %s, username:%s, id: %s" % (
            instagram_user.full_name,
            instagram_user.username,
            instagram_user.id
        )


def instagram_users_query(firstname, lastname):
    query = firstname + " " + lastname
    # user_ids = api.user_search(query, count=3)
    user_ids = api_cycler.api.user_search(query, count=3)
    print "Matches for venmo user %s, %s:" % (lastname, firstname)
    for result in user_ids:
        print '\t%s' % instagram_user_string(result)
    return user_ids


def friend_match_ratio(user, targets):
    user_id = user.id
    if user_id:
        print '%s is following:' % (user.username)
        try:
            # following, next_ = api.user_follows(user_id)
            following, next_ = api_cycler.api.user_follows(user_id)
            for f_user in following:
                print '\tusername=%s, fullname=%s, id=%s' % (
                    f_user.username,
                    f_user.full_name,
                    f_user.id
                )
        except InstagramAPIError as e:
            print e

    return 0.0


def get_one_instagram_user(venmo_user, targets, save=False):
    firstname = venmo_user['firstname']
    lastname = venmo_user['lastname']
    user_id = venmo_user['id']
    instagram_results = instagram_users_query(firstname, lastname)

    for user in instagram_results:
        print friend_match_ratio(user, targets)

    if save:
        saveUser(venmo_user, instagram_results)


def saveUser(target, instagram_results):
    try:
        target_firstname = target['firstname']
        target_lastname = target['lastname']
        target_id = target['id']

        venmo_user_tmp = {}
        if target_id not in venmo_user_ids:
            venmo_user_ids.add(target_id)
            venmo_user_tmp["venmo_id"] = target_id
            venmo_user_tmp["venmo_firstname"] = target_firstname
            venmo_user_tmp["venmo_lastname"] = target_lastname
            venmo_user_tmp["instagram_users"] = []

            for result in instagram_results:
                venmo_user_tmp["instagram_users"].append({"insta_fullname": result.full_name, "insta_id": result.id})
            # if venmousers.find_one({"venmo_id":"venmo_id"}):
            venmousers.save(venmo_user_tmp)
            venmo_user_tmp = {"venmo_id": "", "venmo_firstname": "", "venmo_lastname": "", "instagram_users": []}
    except TypeError:
        print "Found a TypeError"


def main():
    start_time = time.time()

    heavy_users = get_networked_users(trans_collection, limit=50, populate=False)
    match_venmo_instagram(heavy_users)


if __name__ == '__main__':
    main()


