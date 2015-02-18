var https = require('https');
var http = require('http');
var Q = require('q');

//var defaultDest = 'https://venmo.com/api/v5/public';
var defaultDest = 'http://127.0.0.1:8081/1423722113.json'

var httpsGet = function (dest) {
   var deferred = Q.defer();
   https.get(dest || defaultDest, deferred.resolve);
   return deferred.promise;
};

var httpGet = function (dest) {
  var deferred = Q.defer();
  http.get(dest || defaultDest, deferred.resolve);
  return deferred.promise;
};

var loadJSON = function (res) {
  var deferred = Q.defer();
  var body = '';
  res.on('data', function (chunk) {
    body += chunk;
  });
  res.on('error', function(err) {
    deferred.reject(err);
  });
  res.on('end', function () {
    var jsonData;
    try {
      jsonData = JSON.parse(body);
    } catch (err) {
      deferred.reject('Error parsing response to JSON:\n\t' + err);
    }
    return deferred.resolve(jsonData);
  });
  return deferred.promise;
};

exports.vacuumPromise = function (dest) {
  return httpGet(dest).then(function (res) {
  //return httpsGet(dest).then(function (res) {
    return loadJSON(res);
  });
};
