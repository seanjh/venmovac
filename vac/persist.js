var MongoClient = require('mongodb').MongoClient;
var Q = require('q');

var databaseName = 'venmo';
var collectionName = 'trans';
var url = 'mongodb://localhost' + '/' + databaseName;

var saveDataAsync = function (db, data, callback) {
  MongoClient.connect(url, function (err, db) {

    db.close();
    callback(null);
  });
};

exports.savePromise = function (db, data) {
  var deferred = Q.defer();
  saveDataAsync(db. data,  deferred.resolve);
  return deferred.promise;
};

exports.connect = function (db) {
  if (db === undefined) {
    console.log('CONNECT!');
    MongoClient.connect(url, function(err, database) {
      if(err) throw err;
      return database;
    });
  } else {
    console.log('A-OK');
    return db;
  }
};