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
    if (!authService.isloggedin()) {
      $location.path('/welcome');
    }
    else {
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
    $timeout(errorHandler, 20000); // show error if no watchlist after 20 secs
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
    } else if (data.msgtype === 'diff_response') {
      dataService.diffResponseHandler(data)
    } else if (data.msgtype === 'loginerror') {
      $log.error('login failed!');

      $translate(['OAUTH_FAILURE_TITLE', 'OAUTH_FAILURE_CONTENT', 'CLOSE']).then(function (translations) {
        var alert = $mdDialog.alert({
          title: translations['OAUTH_FAILURE_TITLE'],
          content: translations['OAUTH_FAILURE_CONTENT'],
          ok: translations['CLOSE']
        });

        $mdDialog
          .show( alert )
          .finally(function() {
            alert = undefined;
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
        var alert = $mdDialog.alert({
          title: translations['SERVER_ERROR_TITLE'],
          content: translations['SERVER_ERROR_CONTENT'],
          ok: translations['CLOSE']
        });

        $mdDialog
          .show(alert)
          .finally(function () {
            alert = undefined;
          });
      });
    }
  }
}
