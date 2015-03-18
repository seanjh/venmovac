db.trans.aggregate([
  { $match: { $text: { $search: "rent bills utilities"}}},
  { $match: { "actor.external_id": { $exists: true } } },
  { $match: { "transactions.0.target.external_id": { $exists: true } } },
  { $unwind: "$transactions" },
  { $project: {
          payer: "$actor",
          payee: "$transactions.target"
      }},
  { $limit: 1000 }
]);
