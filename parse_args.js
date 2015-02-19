var program = require('commander');

module.exports = program
  .version('0.1')
  .option('-n, --hostname <host>', 
    'custom MongoDB hostname. defaults to localhost', 
    'localhost')
  .option('-p, --port <p>', 
    'custom MongoDB port. defaults to 27017', 
    parseInt, 
    27017)
  .option('-d, --db <d>', 
    'custom MongoDB database name. defaults to venmo', 
    'venmo')
  .option('-u, --user <u>', 'optional MongoDB user name')
  .option('-p, --pass <p>', 'optional MongoDB password');