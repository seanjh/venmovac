from pymongo import MongoClient
from bson.son import SON

DATABASE_NAME = 'venmo'
TRANS_COLLECTION_NAME = 'trans'

client = MongoClient('localhost', 27017)
db = client[DATABASE_NAME]
trans_collection = db[TRANS_COLLECTION_NAME]
