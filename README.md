# VenmoVac
VenmoVac is a siphon of the public Venmo recent payments API (https://venmo.com/api/v5/public).

## Setup
VenmoVac requires a running MongoDB server to operate. The remaining dependencies may be installed with npm install.

    npm install

It is recommended that VenmoVac be launched with [pm2](https://github.com/Unitech/pm2 "Unitech/PM2").

    npm install -g pm2

    pm2 start ./venmovac.js

## Usage

    Usage: venmovac [options]
    
    Options:
    -h, --help             output usage information
    -V, --version          output the version number
    -n, --hostname <host>  custom MongoDB hostname. defaults to localhost
    -p, --port <p>         custom MongoDB port. defaults to 27017
    -d, --db <d>           custom MongoDB database name. defaults to venmo
    -u, --user <u>         optional MongoDB user name
    -p, --pass <p>         optional MongoDB password
