'use strict';
angular
  .module('crosswatch')
  .run(runBlock)
;

function runBlock (socket, $rootScope, dataService, $log, $timeout, $translate, amMoment, localStorageService,
                   $mdDialog, authService, $location) {

  /**
   * Redirect if not logged in
   */
  $rootScope.$on('$routeChangeStart', function (event) {
    if (!authService.isLoggedIn()) {
      $location.path('/welcome');
    }
    else {
      dataService.config.username = authService.user();
      $location.path('/');
    }
  });

  /**
   * Set Moment.js language
   * Strange bug, $translate.use() is sometimes undefined if loaded by angular-translate from local storage
   */
  var lang = $translate.use();
  if (typeof lang === "undefined") {
    lang = localStorageService.get('NG_TRANSLATE_LANG_KEY');
    $translate.use(lang);
  }
  amMoment.changeLocale(lang);

  /**
   * Query watchlist on login.
   * Not part of authService to prevent circular dependency.
   */
  $rootScope.$on('login', function () {
    dataService.queryWatchlist();
    $timeout(errorHandler, 10000); // show error if no response after 10 secs
  });

  /**
   * If logged in before sockjs connected, query watchlist again.
   */
  socket.setHandler('open', function () {
    $log.info('sockjs connected');
    dataService.queryWatchlist();
  });

  /**
   * Handle all sockjs incoming messages here.
   */
  var connectionError = true;
  socket.setHandler('message', function (msg) {
    msg = angular.fromJson(msg);
    var data = angular.fromJson(msg.data);
    if (data.msgtype === 'watchlist') {
      dataService.addWatchlistEntries(data.entires);
    } else if (data.msgtype === 'notification') {
      dataService.addNotificationEntries(data)
    } else if (data.msgtype === 'response') {
      dataService.responseHandler(data)
    } else if (data.msgtype === 'ores_scores') {
      dataService.oresScoresHandler(data)
    } else if (data.msgtype === 'canary') {
      connectionError = false;
      // disable loading spinner after 20 sec (no watchlist entries for the time period)
      $timeout(function () {
        dataService.watchlist.loading = false;
      }, 20000)
    } else if (data.msgtype === 'loginerror') {
      $log.error('login failed with: ' + data.errorinfo);
      $translate(['OAUTH_FAILURE_TITLE', 'OAUTH_FAILURE_CONTENT', 'CLOSE'], {error: data.errorinfo})
        .then(function (translations) {
          registerAlert({
            title: translations['OAUTH_FAILURE_TITLE'],
            content: translations['OAUTH_FAILURE_CONTENT'],
            ok: translations['CLOSE']
          });
        });
    } else if (data.msgtype === 'apierror') {
      $log.error('API error: ' + data.errorinfo);
      $translate(['SERVER_ERROR_TITLE', 'API_ERROR_CONTENT', 'CLOSE'], {errorcode: data.errorcode, errorinfo: data.errorinfo})
        .then(function (translations) {
          registerAlert({
            title: translations['SERVER_ERROR_TITLE'],
            content: translations['API_ERROR_CONTENT'],
            ok: translations['CLOSE']
          });
        });
    } else {
      $log.error("Unhandled message: %o", data);
    }

    if (connectionError) {
      connectionError = false;
    }
  });

  /**
   * Show error message if no watchlist entries are retrieved.
   */
  function errorHandler () {
    if (connectionError) {
      $log.warn('No websocket message after 20 seconds.');
      $translate(['SERVER_ERROR_TITLE', 'SERVER_ERROR_CONTENT', 'CLOSE']).then(function (translations) {
        registerAlert({
          title: translations['SERVER_ERROR_TITLE'],
          content: translations['SERVER_ERROR_CONTENT'],
          ok: translations['CLOSE']
        });
      });
    }
  }

  var currentAlert = false;
  var alerts = [];
  /**
   * Register an $mdDialog alert and schedules it to be shown
   * @param arg paramter for $mdDialog.alert()
   */
  function registerAlert (arg) {
    var alert = $mdDialog.alert(arg);
    alerts.push(alert);
    showAlert();
  }
  function showAlert () {
    if (!currentAlert && alerts.length) {
      currentAlert = alerts.shift();
      $mdDialog
        .show(currentAlert)
        .finally(function () {
          currentAlert = false;
          showAlert();
        });
    }
  }
}
