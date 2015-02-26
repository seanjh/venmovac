#!/usr/bin/env node

var fs = require('fs');
var Q = require('q');
var async = require('async');
var moment = require('moment');

var program = require('./parse_args').parse(process.argv);
var vac = require('./vacuum');
var persist = require('./persist');

var db = persist.getDB();
var transQueue = [];
var transMaster = {};
var queueLimit = 200;
var delayMS = 5000; // 5 seconds

function writeJSONData(data) {
  var filename = moment().format('X') + '.json';
  fs.writeFile(filename, JSON.stringify(data, null, 2), function (err) {
      if (err) {
        console.error(err);
      }
    });
};

function checkOneTransaction(tran, callback) {
  if (tran && tran.payment_id && !transMaster[tran.payment_id]) {
    // This payment_id has not been seen recently
    transMaster[tran.payment_id] = true;
    transQueue.push(tran);
  }
  callback();  // async-lib-style callback
};

function checkTransMaster(dataArray) {
  var deferred = Q.defer();
  async.each(dataArray, checkOneTransaction, deferred.resolve);
  return deferred.promise;
};

function printIds(data) {
  for (var i=0; i<data.length; i++) {
    console.log('\t' + data[i].payment_id);
  }
};

function logInsertIds(record, callback) {
  if (record && record._id && record.permalink) {
    console.log('\t' + record.permalink + ' inserted with _id ' + record._id);
    callback(null);
  } else {
    if (!record._id)
      callback("Missing mongodb _id");
    if (!record.permalink)
      callback("Missing venmo permalink");
    if (!record)
      callback("Record is malformed");
  }
}

function handleInsertLogError(err) {
  if (err) console.error(err);
}

function saveTransactionsAsync(num, dataArray, callback) {
  var insertData;
  insertData = dataArray.slice(dataArray.length - num, dataArray.length);
  if (num && insertData.length > 0) {
    persist.insertPromise(insertData).then(function (records) {
      console.log(moment().format() + ' Finished insert of ' + records.length + ' objects');
      async.each(records, logInsertIds,handleInsertLogError);
    });
  }
  callback(null, insertData);
};

function saveNewTransactions(num) {
  // Persist the new data
  var deferred = Q.defer();
    if (num > 0) {
      saveTransactionsAsync(num, transQueue, deferred.resolve);
    } else {
    deferred.resolve({});
  }
  return deferred.promise;
};

function trimMaster(queue, limit, master, trimCount, callback) {
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

function trimQueueAndMaster(queue, limit, master, callback) {
  var trimCount;
  if (queue.length > limit) {
    trimCount = queue.length - limit;
    trimMaster(queue, limit, master, trimCount, function () {
      queue.splice(0, trimCount);
    });
  }
  callback(null);
};

function queueTransactions(data, db) {
  console.log(moment().format() + ' Processing ' + data.length + ' total transactions.');
  var oldQueueCount = transQueue.length;
  var newTranCount;
  checkTransMaster(data).then(function() {
    newTranCount = transQueue.length - oldQueueCount;
    console.log(moment().format() + ' Located ' + newTranCount + ' new transactions.');
    return saveNewTransactions(newTranCount, db);
  }).then(function() {
    trimQueueAndMaster(transQueue, queueLimit, transMaster, function(){});
  });
};

function processAPI() {
  vac.vacuumPromise().then(function (data) {
    // console.log(moment().format() + ': Got response.');
    //writeJSONData(data);
    var dataArray = data.data;
    queueTransactions(dataArray, db);
  }, function (error) {
    console.error('Error: ' + error);
  });
};

function parse_cli() {
  url = 'mongodb://'.concat(
    program.hostname,
    ':'.concat(program.port),
    '/'.concat(program.db)
    );
};

parse_cli();
persist.connect(url, function (err, db) {
  if (err) throw new Error('Cannot connect to database');
  processAPI();
  setInterval(processAPI, delayMS);
});
