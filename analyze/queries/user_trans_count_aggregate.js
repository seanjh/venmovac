db.trans.aggregate([
  { $match: { "actor.external_id": { $exists: true } } },
  { $match: { "transactions.0.target": { $exists: true } } },
  { $unwind: "$transactions" },
  { $group: {
    _id: {
      sender_external_id: "$actor.external_id",
      recipient_external_id: "$transactions.target.external_id"
    },
    count: { $sum: 1 }
  }},
  { $out: "agg_user_tran_counts" }
]);

db.agg_user_tran_counts.aggregate([
  { $sort: { count: -1, _id: 1 }},
  { $limit: 100 }
]);
