var https = require('https');
var Q = require('q');

var defaultDest = 'https://venmo.com/api/v5/public';

var httpsGet = function (dest) {
  // console.log('httpsGet');
   var deferred = Q.defer();
   https.get(dest || defaultDest, deferred.resolve);
   return deferred.promise;
};

var loadJSON = function (res) {
  // console.log('loadJSON');
  var deferred = Q.defer();
  var body = '';
  res.on('data', function (chunk) {
    body += chunk;
  });
  res.on('end', function () {
    deferred.resolve(JSON.parse(body));
  });
  return deferred.promise;
};

exports.vacuumPromise = function (dest) {
  return httpsGet(dest).then(function (res) {
    return loadJSON(res);
  });
};
