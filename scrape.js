var fs = require('fs');
var moment = require('moment');
var vac = require('./vac/vac');

// vac.vacuumPromise().then(console.log);
vac.vacuumPromise().then(function (jsonData) {
  var filename = moment().format('X') + '.json';
  fs.writeFile(filename, JSON.stringify(jsonData, null, 2), function (err) {
    if (err) {
      console.error(err);
    }
  });
});
