var fs = require('fs');
var moment = require('moment');
var vac = require('./vac/vac');

// vac.vacuumPromise().then(console.log);

setInterval(function () {
  vac.vacuumPromise().then(function (jsonData) {
    console.log('Got JSON');
    var filename = moment().format('X') + '.json';
    fs.writeFile(filename, JSON.stringify(jsonData, null, 2), function (err) {
      if (err) {
        console.error(err);
      }
    });
  });
}, 60000);
