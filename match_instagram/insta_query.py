import sys
import time
import argparse

from instagram.client import InstagramAPI
from instagram.bind import InstagramAPIError

from mongo_helper import (
    CLIENT,
    DB,
    TRANS_COLLECTION,
    USER_PAIRS_COLLECTION,
    VENMO_INSTAGRAM_MATCHES,
    VENMO_INSTAGRAM_CACHE
)
from instagram_helper import InstagramAPICycler, get_all_paginated_data

parser = argparse.ArgumentParser()
parser.add_argument('tokens',
    nargs='+',
    help='Instagram OAuth access tokens'
)
parser.add_argument('-rv',
    action='store_true',
    dest='redo_venmo_heavies',
    help='Repopulate heavy Venmo users data from Venmo transactions'
)
parser.add_argument('-t', '--threshold',
    dest='threshold',
    type=int,
    default=50,
    help='Threshold number of unique Venmo users transacted after which some user is considered a "heavy user" (default: 50)'
)


INSTAGRAM_QUERIED_SET = set()
VENMO_IDS_SET = set()


def match_venmo_instagram(user_pairs):
    for result in user_pairs:
        user = result.get('_id')
        targets = result.get('targets')
        get_one_instagram_user(user, targets)


def populate_user_pairs_collection(source_collection):
    print '------RE-POPULATING MONGODB COLLECTION user_pairs------'
    start = time.time()

    USER_PAIRS_COLLECTION.drop()
    print 'Dropped existing user_pairs collection. Completed in %f seconds.' % (time.time() - start)

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
    start = time.time()

    result = source_collection.aggregate(pipeline, allowDiskUse=True)
    print 'Completed aggregate query of trans collection. Completed in %f seconds.' % (time.time() - start)


def get_networked_users(source_collection, threshold, populate=True):
    if populate:
        populate_user_pairs_collection(source_collection)

    print '------FINDING VENMO USERS WITH >%d TARGET USERS------' % threshold

    # Finds matches using an array index, so value to match is threshold-1
    targets_index_str = "targets.%d" % (threshold - 1)

    pipeline = [
        {"$match": {targets_index_str: {"$exists": True }}},
        {"$unwind": "$targets"},
        {"$group": {
            "_id": "$_id",
            "total_targets": {"$sum": 1}
        }},
        {"$sort": {"total_targets": -1}}
    ]

    start = time.time()
    cursor = USER_PAIRS_COLLECTION.aggregate(pipeline)
    print 'Completed aggregate query of user_pairs collection. Completed in %f seconds.' % (time.time() - start)

    print
    heavy_users = []
    for result in cursor:
        if result.get('_id') and result['_id'].get('username'):
            pairs = get_pairs_for_user(result.get('_id'))
            print 'Venmo user %s transacted with %d other users' % (
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


def checked_venmo_instagram_users():
    print '\n------RETURNING PREVIOUSLY QUERIED VENMO INSTAGRAM USERS------'

    start = time.time()

    results = VENMO_INSTAGRAM_CACHE.find()

    print 'Completed finding existing venmo-instagram matches in %f seconds.' % (time.time() - start)
    return [user_id.get('_id') for user_id in results]


def instagram_users_query(firstname, lastname):
    query = firstname + " " + lastname
    user_ids = API_CYCLER.api.user_search(query, count=3)
    return user_ids


def friend_match_ratio(instagram_user, targets):
    following = []
    match_count = 0
    matches = list()
    user_id = instagram_user.id
    if user_id:
        try:
            # following = get_all_instagram_following(user_id)
            following = get_all_paginated_data(API_CYCLER.api, 'user_follows', user_id=user_id)
            for i, following_user in enumerate(following):
                venmo_target_match = match_instagram_to_venmo_users(following_user, targets)
                if venmo_target_match:
                    match_count += 1
                    matches.append({
                        "venmo": venmo_target_match,
                        "instagram": following_user
                    })
                else:
                    # Couldn't match instagram following user to venmo targets user
                    pass
        except InstagramAPIError as e:
            if (e.status_code == 400):
                print "ERROR: Instagram user %s -- %s is set to private." % (instagram_user.username, instagram_user.id)
            return -1.0, matches

    print '\tInstagram username %s (%s) matched %d Instagram followers to %d Venmo targets -- %0.3f%%' % (
        instagram_user.username, instagram_user.full_name, len(following), match_count,
        float(match_count) / len(following) * 100 if len(following) > 0 else 0.0
    )
    if len(following) > 0:
        return float(len(matches)) / len(following), matches
    else:
        return 0.0, matches


def match_instagram_to_venmo_users(instagram_user, venmo_users):
    # Just grab 2 pieces of the Instagram full_name (split on whitespace)
    i_name_parts = instagram_user.full_name.lower().split(None, 2)

    i_firstname = i_name_parts[0] if len(i_name_parts) > 1 and len(i_name_parts[0]) > 1 else None
    i_lastname = i_name_parts[1] if len(i_name_parts) > 1 and len(i_name_parts[1]) > 1 else None

    for v_user in venmo_users:
        v_firstname = v_user.get('firstname').lower()
        v_lastname = v_user.get('lastname').lower()
        if i_lastname and v_lastname == i_lastname and v_firstname == i_firstname:
            print '\tTarget Venmo user %s (%s, %s) matched following Instagram user %s (username=%s, id=%s)' % (
                v_user.get('username'),
                v_user.get('name'),
                v_user.get('id'),
                instagram_user.full_name,
                instagram_user.username,
                instagram_user.id
            )
            return v_user
    return None


def cache_venmo_queried_user(venmo_user):
    user_id = int(venmo_user['id'])
    # print 'Queried Instagram set %s' % INSTAGRAM_QUERIED_SET
    INSTAGRAM_QUERIED_SET.add(user_id)
    VENMO_INSTAGRAM_CACHE.save({
        "_id": user_id
    })


def get_best_instagram_match(venmo_user, instagram_results, targets):
    print '\n\n------BEGINNING VENMO INSTAGRAM MATCHER------'
    print 'Venmo user %s (%s, %s) matched %d possible Instagram users: %s' % (
        venmo_user.get('username'),
        venmo_user.get('name'),
        venmo_user.get('id'),
        len(instagram_results),
        [user.username for user in instagram_results]
    )

    ratios = []
    matches = []
    for i, user in enumerate(instagram_results):
        print '%d/%d: Checking Instagram users following %s (%s) against Venmo target users' % (
            i+1, len(instagram_results), user.username, user.full_name
        )
        ratio, target_matches = friend_match_ratio(user, targets)
        ratios.append(ratio)
        matches.append(target_matches)

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
        print 'BEST MATCH LOCATED'
        print '\tVenmo:     %s (full_name=%s)' % (venmo_user['username'], venmo_user['name'])
        print '\tInstagram: %s (full_name=%s, id=%s)' % (instagram_match.username, instagram_match.full_name, instagram_match.id)
    else:
        print 'NO MATCH on Instagram for Venmo user %s (%s)' % (venmo_user['username'], venmo_user['name'])

    return instagram_match, max_index, matches


def get_one_instagram_user(venmo_user, targets, save=True):
    venmo_user_id = venmo_user['id']
    if int(venmo_user_id) not in INSTAGRAM_QUERIED_SET:
        instagram_results = instagram_users_query(venmo_user['firstname'], venmo_user['lastname'])
        cache_venmo_queried_user(venmo_user)

        if len(instagram_results) > 0:
            instagram_match, max_index, matches = get_best_instagram_match(
                venmo_user,
                instagram_results,
                targets
            )

            if save and instagram_match is not None:
                save_user_match(venmo_user, instagram_match)
                for match in matches[max_index]:
                    save_user_match(
                        match.get('venmo'),
                        match.get('instagram'),
                        user_type='target',
                        actor_id=venmo_user.get('id')
                    )


def get_instagram_user_dict(user):
    attributes = ["username", "id", "full_name", "profile_picture", "bio", "website"]
    user_dict = {}
    for attrib in attributes:
        if hasattr(user, attrib):
            user_dict[attrib] = getattr(user, attrib)
    return user_dict


def save_user_match(venmo_user, instagram_user, user_type='actor', actor_id=None):
    venmo_id = int(venmo_user['id'])

    document = {
        "_id":          venmo_id,
        "venmo":        venmo_user,
        "instagram":    get_instagram_user_dict(instagram_user),
        "user_type":    user_type
    }

    if actor_id:
        document["actor_id"] = actor_id

    if venmo_id not in VENMO_IDS_SET:
        VENMO_IDS_SET.add(venmo_id)



def filter_users_to_query(users):
    filtered_users = []
    old_user_ids = checked_venmo_instagram_users()
    for user in users:
        try:
            user_id = int(user.get('_id').get('id'))
            if user_id not in old_user_ids:
                filtered_users.append(user)
        except TypeError as e:
            print e
            continue

    return filtered_users


def clear_previously_matched_users_cache():
    VENMO_INSTAGRAM_CACHE.drop()


def get_instagram_media():
    user_matches = get_venmo_instagram_matches()


def get_venmo_instagram_matches():
    return VENMO_INSTAGRAM_MATCHES.find()

def get_instagram_user_media(user):
    pass


def main():
    args = parser.parse_args()

    access_tokens = []
    access_token = None
    if args.tokens:
        access_tokens = args.tokens
        access_token = access_tokens[-1]
    else:
        access_token = ""

    if access_tokens:
        API_CYCLER = InstagramAPICycler(access_tokens)
    else:
        API_CYCLER = InstagramAPICycler([access_token])

    heavy_users = get_networked_users(
        TRANS_COLLECTION,
        threshold=args.threshold,
        populate=args.redo_venmo_heavies
    )

    if args.redo_venmo_heavies:
        clear_previously_matched_users_cache()
    else:
        old_len = len(heavy_users)
        heavy_users = filter_users_to_query(heavy_users)
        print 'Filtered Venmo users to query from %d to %d' % (old_len, len(heavy_users))

    match_venmo_instagram(heavy_users)

    get_instagram_media()


if __name__ == '__main__':
    main()