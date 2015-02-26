var https = require('https');
var Q = require('q');

var defaultDest = 'https://venmo.com/api/v5/public';

var httpsGet = function (dest) {
   var deferred = Q.defer();
   https.get(dest || defaultDest, deferred.resolve);
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
  return httpsGet(dest).then(function (res) {
    return loadJSON(res);
  });
};
