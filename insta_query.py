import time
import argparse

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
        self._pos = (self._pos + 1) % len(self._tokens)
        return the_api.get('api_object')


if access_tokens:
    API_CYCLER = InstagramAPICycler(access_tokens)
else:
    API_CYCLER = InstagramAPICycler([access_token])

CLIENT = pymongo.MongoClient('localhost', 27017)
DB = CLIENT['venmo']

TRANS_COLLECTION = DB['trans']
USER_PAIRS_COLLECTION = DB['user_pairs']
VENMO_USERS_COLLECTION = DB['venmo_users']
VENMO_USERS_COLLECTION.create_index("venmo_id")

VENMO_IDS_SET = set()


def match_venmo_instagram(user_pairs):
    for result in user_pairs:
        user = result.get('_id')
        targets = result.get('targets')
        get_one_instagram_user(user, targets)


def populate_user_pairs_collection(trans_collection):
    print '------RE-POPULATING MONGODB COLLECTION user_pairs------'

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

    print '------FINDING VENMO USERS WITH >%d TARGET USERS------' % limit

    # Finds matches using an array index, so value to match is limit-1
    targets_index_str = "targets.%d" % (limit - 1)

    pipeline = [
        {"$match": {targets_index_str: {"$exists": True }}},
        {"$unwind": "$targets"},
        {"$group": {
            "_id": "$_id",
            "total_targets": {"$sum": 1}
        }},
        {"$sort": {"total_targets": -1}}
    ]
    cursor = USER_PAIRS_COLLECTION.aggregate(pipeline)

    heavy_users = []
    for result in cursor:
        if result.get('_id') and result['_id'].get('username'):
            pairs = get_pairs_for_user(result.get('_id'))
            print '%s Targets: %d' % (
                result['_id'].get('username'),
                len(pairs.get('targets')) if pairs.get('targets') else -1
            )
            heavy_users.append(pairs)

    return heavy_users


def get_pairs_for_user(user):
    external_id = user.get('external_id')
    results = [r for r in USER_PAIRS_COLLECTION.find(
        {"_id.external_id": external_id}
    )]
    if results:
        return results[0]
    return None


def instagram_user_string(instagram_user):
    return "fullname: %s, username:%s, id: %s" % (
        instagram_user.full_name,
        instagram_user.username,
        instagram_user.id
    )


def instagram_users_query(firstname, lastname):
    query = firstname + " " + lastname
    user_ids = API_CYCLER.api.user_search(query, count=3)
    return user_ids


def get_all_instagram_following(instagram_id):
    following = []
    tmp_follow, next_ = API_CYCLER.api.user_follows(instagram_id)
    following.extend(tmp_follow)

    while next_:
        tmp_follow, next_ = API_CYCLER.api.user_follows(with_next_url=next_)
        following.extend(tmp_follow)
    return following


def friend_match_ratio(user, targets):
    following = []
    match_count = 0
    user_id = user.id
    if user_id:
        try:
            following = get_all_instagram_following(user_id)
            for i, f_user in enumerate(following):
                if is_instagram_user_venmo_target(f_user, targets):
                    match_count += 1
                else:
                    # Couldn't match instagram following user to venmo targets user
                    pass
        except InstagramAPIError as e:
            print '\tInstagramAPIError: Could not fetch followers for Instagram user %s -- %s' % (
                user.username, e
            )
            return -1.0

    print '\tInstagram username %s (%s) matched %d Instagram followers to %d Venmo targets -- %0.3f%%' % (
        user.username, user.full_name, len(following), match_count,
        float(match_count) / len(following) * 100 if len(following) > 0 else 0.0
    )
    if len(following) > 0:
        return float(match_count) / len(following)
    else:
        return 0.0


def is_instagram_user_venmo_target(instagram_user, venmo_users):
    # Just grab 2 pieces of the Instagram full_name (split on whitespace)
    i_name_parts = instagram_user.full_name.lower().split(None, 2)

    i_firstname = i_name_parts[0] if len(i_name_parts) > 1 and len(i_name_parts[0]) > 1 else None
    i_lastname = i_name_parts[1] if len(i_name_parts) > 1 and len(i_name_parts[1]) > 1 else None

    for v_user in venmo_users:
        v_firstname = v_user.get('firstname').lower()
        v_lastname = v_user.get('lastname').lower()
        if i_lastname and v_lastname == i_lastname and v_firstname == i_firstname:
            print '\tTarget Venmo user %s (%s) matched following Instagram user %s (username=%s, id=%s)' % (
                v_user.get('username'),
                v_user.get('name'),
                instagram_user.full_name,
                instagram_user.username,
                instagram_user.id
            )
            return True
    return False


def get_one_instagram_user(venmo_user, targets, save=True):
    firstname = venmo_user['firstname']
    lastname = venmo_user['lastname']
    instagram_results = instagram_users_query(firstname, lastname)
    if len(instagram_results) == 0:
        return

    print
    print
    print '------BEGINNING VENMO INSTAGRAM MATCHER------'
    print 'Venmo user %s (%s) matched %d possible Instagram users: %s' % (
        venmo_user['username'],
        venmo_user['name'],
        len(instagram_results),
        [user.username for user in instagram_results]
    )

    ratios = []
    for i, user in enumerate(instagram_results):
        print '%d/%d: Checking Instagram users following %s (%s) against Venmo target users' % (
            i+1, len(instagram_results), user.username, user.full_name
        )
        ratios.append(friend_match_ratio(user, targets))

    print '------INSTAGRAM MATCHER RESULTS------'
    max_ratio = None
    max_index = None
    for i, ratio in enumerate(ratios):
        if ratio > 0 and (max_ratio is None or ratio > max_ratio):
            max_ratio = ratio
            max_index = i

    instagram_match = None
    if max_index is not None:
        instagram_match = instagram_results[max_index]
        print '\tBEST MATCH'
        print '\tVenmo:     %s (full_name=%s)' % (venmo_user['username'], venmo_user['name'])
        print '\tInstagram: %s (full_name=%s, id=%s)' % (instagram_match.username, instagram_match.full_name, instagram_match.id)
    else:
        print '\tNO MATCH on Instagram for Venmo user %s (%s)' % (venmo_user['username'], venmo_user['name'])
        print ratios

    if save and instagram_match:
        saveUser(venmo_user, instagram_match)


def saveUser(target, instagram_results):
    try:
        target_firstname = target['firstname']
        target_lastname = target['lastname']
        target_id = target['id']

        venmo_user_tmp = {}
        if target_id not in VENMO_IDS_SET:
            VENMO_IDS_SET.add(target_id)
            venmo_user_tmp["venmo_id"] = target_id
            venmo_user_tmp["venmo_firstname"] = target_firstname
            venmo_user_tmp["venmo_lastname"] = target_lastname
            venmo_user_tmp["instagram_users"] = []

            for result in instagram_results:
                venmo_user_tmp["instagram_users"].append({"insta_fullname": result.full_name, "insta_id": result.id})
            # if venmousers.find_one({"venmo_id":"venmo_id"}):
            VENMO_USERS_COLLECTION.save(venmo_user_tmp)
            venmo_user_tmp = {"venmo_id": "", "venmo_firstname": "", "venmo_lastname": "", "instagram_users": []}
    except TypeError:
        print "Found a TypeError"


def main():
    heavy_users = get_networked_users(TRANS_COLLECTION, limit=30)
    match_venmo_instagram(heavy_users)


if __name__ == '__main__':
    main()


