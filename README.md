# crosswatch

Crosswatch is an enhanced cross-wiki watchlist for Wikimedia projects running at
[tools.wmflabs.org/crosswatch](http://tools.wmflabs.org/crosswatch/).

It uses a Python based backend and a AngularJS based frontend.

```
git clone https://git.wikimedia.org/git/labs/tools/crosswatch.git
cd crosswatch
```

##Frontend
Install the local dependencies
```
sudo npm install -g gulp bower
cd frontend
npm install
bower install --production
```

While developing use `gulp serve` to preview changes and `gulp build` to
build the application to `frontend/dist` for deployment.

##Backend
First change `config.py` to use your credentials.
```
cd backend
cp config.py.sample config.py
```
Then create a virtualenv and run
```
cd ..
python setup.py install
```

Start the Tornado webserver on `$PORT` with
```
python -m backend $PORT
```
and the a celery worker:
```
celery -A backend worker -l info
```

There are some helpful scripts if the tool runs on [Tool Labs](https://wikitech.wikimedia.org/wiki/Nova_Resource:Tools) in the `scripts`
directory. Change the name of the tool in `frontend/gulpfile.js` and
`backend/config.py` and the `scripts` files.

#License
Licensed under [ISC](https://en.wikipedia.org/w/index.php?title=ISC_license&oldid=653545972)
