var actor_id = "1497902";
db.trans.aggregate([
  {$match: {"actor.id": actor_id}},
  {$unwind: "$transactions"},
  {$project: {
    "actor.username": 1,
    "actor.id": 1,
    "transactions.target.username": 1,
    "transactions.target.id": 1,
    "created_time": 1,
    "updated_time": 1
  }},
  {$sort: {"created_time": -1}}
]);