var wcMap = function () {
  var words = this.message.toLowerCase().match(/\S+/g);
  words.forEach(function (word) {
    if (word.length > 100) {
      emit(word.slice(0, 100), 1);
    } else {
      emit(word, 1);
    }
  });
};

var wcReduce = function (wordKey, wordValues) {
  var count = wordValues.reduce(function(prev, next) {
    return prev + next;
  }, 0);
  return count;
};

db.trans.mapReduce(
  wcMap,
  wcReduce,
  { out: {merge: "mr_message_word_count"} }
);

// Get top 100 words
db.mr_message_word_count.aggregate([
    {$sort: {"value": -1}},
    {$limit: 100}
]);
