'use strict';
angular
  .module('crosswatch', [
    'ngAnimate',
    'ngSanitize',
    'ngRoute',
    'ngMaterial',
    'LocalStorageModule',
    'pascalprecht.translate',
    'angular-translate-storage',
    'bd.sockjs',
    'angularMoment',
    'infinite-scroll'
  ])
  .config(routeConfig)
  .config(locationConfig)
  .config(storageConfig)
  .factory('socket', socketFactory)
  .directive('stopEvent', stopEventDirective)
;

function routeConfig ($routeProvider) {
  $routeProvider
    .when('/', {
      templateUrl: 'app/main/main.html',
      controller: 'MainCtrl',
      controllerAs: 'ctrl'
    })
    .when('/welcome', {
      templateUrl: 'app/welcome/welcome.html'
    })
    .otherwise({
      redirectTo: '/'
    });
}

function locationConfig ($locationProvider) {
  // use the HTML5 History API
  $locationProvider.html5Mode({
    enabled: true,
    requireBase: true
  });
}

function storageConfig (localStorageServiceProvider) {
  localStorageServiceProvider
    .setPrefix('crosswatch')
    .setStorageCookie(30, '/crosswatch/');
}

function socketFactory (socketFactory, $browser, $location) {
  var baseHref = $browser.baseHref();
  var sockjsUrl = baseHref + 'sockjs';
  if ($location.host() === 'localhost') { // debug – use tools backend when developing
    sockjsUrl = 'https://tools.wmflabs.org/crosswatch/sockjs'
  }

  return socketFactory({
    url: sockjsUrl
  });
}

/**
 * Stop click event propagation
 */
function stopEventDirective() {
  return {
    restrict: 'A',
    link: function (scope, element, attr) {
      element.bind('click', function (e) {
        e.stopPropagation();
      });
    }
  };
}
