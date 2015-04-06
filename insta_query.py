from instagram.client import InstagramAPI
from instagram.bind import InstagramAPIError
import pymongo
import time
from math import *

access_token = ""
api = InstagramAPI(access_token=access_token)

CLIENT = pymongo.MongoClient('localhost', 27017)
DB = CLIENT['venmo']
collection = DB['trans']
venmousers = DB['venmo_users']
venmousers.create_index("venmo_id")
venmo_user_ids = []

def saveUser(target): 
	try:
		target_firstname = target['firstname']
		target_lastname =  target['lastname']
		target_id = target['id']

		venmo_user_tmp = {}
		if target_id not in venmo_user_ids:
			venmo_user_ids.append(target_id)
			venmo_user_tmp["venmo_id"] = target_id
			venmo_user_tmp["venmo_firstname"] = target_firstname
			venmo_user_tmp["venmo_lastname"] = target_lastname
			venmo_user_tmp["instagram_users"] = []
		
			query = target_firstname + " " + target_lastname
			user_ids = api.user_search(query, count = 3)
		
			for result in user_ids:
				venmo_user_tmp["instagram_users"].append({"insta_fullname":result.full_name,"insta_id":result.id})
			# if venmousers.find_one({"venmo_id":"venmo_id"}):
			venmousers.save(venmo_user_tmp)
			venmo_user_tmp = {"venmo_id":"", "venmo_firstname":"", "venmo_lastname":"", "instagram_users":[]}
	except TypeError:
		print "Found a TypeError"
		
count = 0
start_time = time.time()

for doc in collection.find():
	count += 1	
	if count % 100 == 0:
		print "We are doc " + str(count)
		print("--- %s seconds ---" % (time.time() - start_time))
	saveUser(doc['transactions'][0]['target'])
	saveUser(doc['actor'])

	
	


	
