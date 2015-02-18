var fs = require('fs');
var Q = require('q');
var async = require('async');
var moment = require('moment');
var vac = require('./vac');
var persist = require('./persist');

var transQueue = [];
var transMaster = {};
var queueLimit = 200;
var delayMS = 60000; // 10 seconds
var db;

var writeJSONData = function (data) {
  var filename = moment().format('X') + '.json';
  fs.writeFile(filename, JSON.stringify(data, null, 2), function (err) {
      if (err) {
        console.error(err);
      }
    });
};

var checkOneTransaction = function (tran, callback) {
  if (tran && tran.payment_id && !transMaster[tran.payment_id]) {
    // This payment_id has not been seen recently
    transMaster[tran.payment_id] = true;
    transQueue.push(tran);
  }
  callback();  // async-lib-style callback
};

var checkTransMaster = function (dataArray) {
  var deferred = Q.defer();
  async.each(dataArray, checkOneTransaction, deferred.resolve);
  return deferred.promise;
};

var printIds = function (data) {
  for (var i=0; i<data.length; i++) {
    console.log('\t' + data[i].payment_id);
  }
};

var saveTransactionsAsync = function(num, dataArray, callback) {
  var insertData;
  if (num) {
    insertData = dataArray.slice(dataArray.length - num, num);
    persist.savePromise(db, insertData).then(function(){});
    //printIds(insertData);
  }
  callback(null, insertData);
};

var saveNewTransactions = function (num) {
  // Persist the new data
  var deferred = Q.defer();
    if (num > 0) {
      // TODO: insert slice
      saveTransactionsAsync(num, transQueue, deferred.resolve);
      console.log('DO INSERT');
    } else {
    deferred.resolve({});
  }
  return deferred.promise;
};

var trimMaster = function (queue, limit, master, trimCount, callback) {
  // Trim transaction queue to below limit if necessary
  var transToTrash;
  if (queue.length > limit) {
    transToTrash = queue.slice(0, trimCount);
    async.each(transToTrash, function (data) {
      delete master[data.payment_id];
    }, function () {
    });
    callback(null);
  }
};

var trimQueueAndMaster = function (queue, limit, master, callback) {
  var trimCount;
  if (queue.length > limit) {
    trimCount = queue.length - limit;
    trimMaster(queue, limit, master, trimCount, function () {
      queue.splice(0, trimCount);
    });
  }
  callback(null);
};

var queueTransactions = function (data, db) {
  console.log(moment().format() + ': Processing ' + data.length + ' total transactions.');
  var oldQueueCount = transQueue.length;
  var newTranCount;
  checkTransMaster(data).then(function() {
    newTranCount = transQueue.length - oldQueueCount;
    console.log(moment().format() + ': Located ' + newTranCount + ' new transactions.');
    return saveNewTransactions(newTranCount, db);
  }).then(function() {
    trimQueueAndMaster(transQueue, queueLimit, transMaster, function(){});
  });
  console.log(moment().format() + ': Completed processing transactions.');
};

// TODO: get DB
// http://mongodb.github.io/node-mongodb-native/1.4/driver-articles/mongoclient.html#the-url-connection-format
setInterval(function () {
  vac.vacuumPromise().then(function (data) {
    console.log(moment().format() + ': Got response.');
    //writeJSONData(data);
    var dataArray = data.data;
    queueTransactions(dataArray, db);
  }, function (error) {
    console.error('Error: ' + error);
  });
}, delayMS);
