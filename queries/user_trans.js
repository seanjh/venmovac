var user_id = '1668182';
db.trans.aggregate([
  {$unwind: "$transactions"},
  {$match: {
    $or: [
      {"actor.id": user_id},
      {"transactions.target.id": user_id}
    ]}
  },
  {$sort: {"created_time": 1}}
]);