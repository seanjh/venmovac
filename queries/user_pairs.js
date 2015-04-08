db.trans.aggregate(
  [
    { $match: { "actor.external_id": { $exists: true } } },
    { $match: { "transactions.0.target.external_id": { $exists: true } } },
    { $unwind: "$transactions" },
    { $group: {
      _id: "$actor",
      targets: { $addToSet: "$transactions.target" }
    }},
    { $out: "user_pairs" },
  ],
  { allowDiskUse: true }
);

// Users that transacted with at least 20 other users
db.user_pairs.aggregate([
  { $match: { "targets.19": { $exists: true } } },
  { $unwind: "$targets" },
  { $group: {
    _id: "$_id",
    total_targets: { $sum: 1 }
  }},
  { $sort: { total_targets: -1 } }
]);