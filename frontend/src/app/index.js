'use strict';
angular
  .module('watchr', [
    'ngAnimate',
    'ngSanitize',
    'ngCookies',
    'ngRoute',
    'mgcrea.ngStrap',
    'pascalprecht.translate',
    'bd.sockjs',
    'angularMoment'
  ])
  .config(function ($routeProvider) {
    $routeProvider
      .when('/', {
        templateUrl: 'app/main/main.html',
        controller: 'MainCtrl',
        controllerAs: 'ctrl'
      })
      .otherwise({
        redirectTo: '/'
      });
  })
  .config(function ($locationProvider) {
    // use the HTML5 History API
    $locationProvider.html5Mode({
      enabled: true,
      requireBase: true
    });
  })
  .filter('numberformat', function ($filter) {
    return function (x) {
      var result = $filter('number')(x);
      if (x >= 0) {
        result = '+' + result;
      }
      return result;
    }
  })
  .factory('socket', function (socketFactory, $browser, $location) {
    var baseHref = $browser.baseHref();
    var sockjsUrl = baseHref + 'sockjs';
    if ($location.host() === 'localhost') { // debug
      sockjsUrl = 'https://tools.wmflabs.org/watchr/sockjs'
    }

    return socketFactory({
      url: sockjsUrl
    });
  })
  .service('authService', function ($cookies, $rootScope, $log) {
    $rootScope.$watch(function () { return $cookies.watchrUser;}, function (newValue) {
      if (typeof(newValue) !== 'undefined') {
        $log.info('Singed in as ' + newValue);
        $rootScope.$emit('login', newValue);
      }
    });

    this.tokens = function () {
      return angular.fromJson(($cookies.watchrAuth).replace(/\\054/g, ','));
    };

    this.user = function () {
      return $cookies.watchrUser;
    };

    this.isloggedin = function () {
      return (typeof($cookies.watchrAuth) !== 'undefined');
    };

  })
  .run(function (amMoment, $translate, socket, $rootScope, authService, $log) {
    amMoment.changeLocale($translate.use());

    socket.setHandler('open', function () {
      $log.info('sockjs connected');
      queryWatchlist();
    });

    socket.setHandler('message', function (msg) {
      msg = angular.fromJson(msg);
      $log.info(msg);
      if (msg.msgtype === 'loginerror') {
        $log.error('failedlogin');
        $rootScope.$emit('error', 'loginerror');
      }
    });

    $rootScope.$on('login', function () {
      try {
        queryWatchlist();
      } catch(err) {
        if (err.message !== 'INVALID_STATE_ERR') {
         $log.error(err);
        }
      }
    });

    function queryWatchlist() {
      if (authService.isloggedin()) {
        var watchlistQuery = {
          action: 'watchlist',
          access_token: authService.tokens()
        };
        socket.send(angular.toJson(watchlistQuery));
      }
    }
  })
;

