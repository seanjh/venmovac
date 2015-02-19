var MongoClient = require('mongodb').MongoClient;
var Q = require('q');

var databaseName = 'venmo';
var collectionName = 'trans';
var _url = 'mongodb://localhost' + '/' + databaseName;
var _db;

module.exports = {
  connect: function connect(url, callback) {
    if (url) {
      _url = url;
    }
    MongoClient.connect(_url, function (err, db) {
      _db = db;
      return callback(err, _db);
    });
  },

  close: function close() {
    _db.close();
  },

  getDB: function getDB() {
    return _db;
  },

  getURL: function getURL() {
    return _url;
  },

  insertPromise: function insertPromise(data) {
   var deferred = Q.defer();
    var collection = _db.collection(collectionName);
    collection.insert(data, function (err, records) {
      if (err) { return deferred.reject(err); }
      return deferred.resolve(records);
    });
    return deferred.promise;
  }
};
