import pymongo

CLIENT = pymongo.MongoClient('localhost', 27017)
DB = CLIENT['venmo']

"""
    Collection: trans
    Holds data pulled directly from the public Venmo API.
"""
TRANS_COLLECTION = DB['trans']

"""
    Collection: user_pairs
    Holds 1 Venmo user object, and all the other unique Venmo user objects that
    were the target of that user's transactions. This data is derived from the
    main trans collection.

    Schema:
    {
        "_id":      { [Venmo user object, payer] },
        "targets:   [array of >0 target Venmo user objects]
    }
"""
USER_PAIRS_COLLECTION = DB['user_pairs']

"""
    Collection: venmo_instagram
    Holds 1 user object from venmo and 1 user object from instagram representing
    the same individual person (hopefully).

    Schema:
    {
        "_id":          [Venmo user id],
        "venmo":        { [Venmo user object] },
        "instagram":    { [Instagram user object] },
        "type":         [ "actor" (payer) or "target" (recipient) ],
        "actor_id":     [(optional) Venmo user id (actor) for target users]

    }
"""
VENMO_INSTAGRAM_MATCHES = DB['venmo_instagram']
VENMO_INSTAGRAM_MATCHES.create_index("venmo_id")

"""
    Collection: instagram_api_cache
    Holds Venmo user ids that have been checked on instagram.
"""
VENMO_INSTAGRAM_CACHE = DB['instagram_api_cache']