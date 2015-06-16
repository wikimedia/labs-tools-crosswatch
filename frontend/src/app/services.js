'use strict';
angular
  .module('crosswatch')
  .service('authService', authService)
  .service('dataService', dataService)
  .factory('debounce', debounceService)
;

function authService (localStorageService, $rootScope, $log) {
  $rootScope.$watch(function () { return localStorageService.cookie.get('user');}, function (newValue) {
    if (newValue !== null) {
      $log.info('Singed in as ' + newValue);
      $rootScope.$emit('login', newValue);
    }
  });

  this.tokens = function () {
    return angular.fromJson(localStorageService.cookie.get('auth').replace(/\\054/g, ','));
  };

  this.user = function () {
    return localStorageService.cookie.get('user');
  };

  this.isloggedin = function () {
    return (localStorageService.cookie.get('auth') !== null);
  };

}

function dataService (socket, authService, localStorageService, $log, $filter, debounce) {
  var vm = this;

  vm.watchlist = {};
  /**
   * Array that contains all watchlist entries.
   */
  vm.watchlist.original = [];
  /**
   * Array that contains the filtered watchlist entries.
   */
  vm.watchlist.filtered = [];
  /**
   * Part of watchlist.filtered which is displayed
   */
  vm.watchlist.active = [];

  /**
   * Initialize user settings
   */
  vm.defaultconfig = {
    /**
     * true: show only latest change
     * false: show all changes
     */
    lastrevonly: false,
    /**
     * Timeperiod for which the watchlist is retrieved in days
     */
    watchlistperiod: 1.5,
    flagsenable: false,
    /**
     * Options to show minor, bot, anon and registered user edits
     */
    editflags: false,
    /**
     * List of all known projects (wikis)
     */
    projectsList: false,
    /**
     * List of selected projects (wikis)
     */
    projectsSelected: false
  };
  if (localStorageService.get('config') !== null) {
    vm.config = localStorageService.get('config');
    vm.config.__proto__ = vm.defaultconfig;
  } else {
    vm.config = Object.create(vm.defaultconfig);
  }
  // Sadly no other way to do this right
  vm.config.projectsList = vm.config.projectsList || [];
  vm.config.projectsSelected = vm.config.projectsSelected || [];
  vm.config.editflags = vm.config.editflags || {
      minor: true,
      bot: false,
      anon: true,
      registered: true
    };

  /**
   * Process an array of new watchlist entries.
   * @param entries
   */
  vm.addWatchlistEntries = function (entries) {
    Array.prototype.push.apply(vm.watchlist.original, entries);
    vm.watchlist.original.sort(function(a,b){
      return new Date(b.timestamp) - new Date(a.timestamp);
    });

    var project = entries[0].project;
    if (vm.config.projectsList.indexOf(project) === -1) {
      vm.config.projectsList.push(project);
      vm.config.projectsSelected.push(project);
      vm.saveConfig();
    }

    vm.filterWatchlistDebounced();
  };

  /**
   * Display more watchlist entries
   */
  vm.moreWatchlistEntries = function () {
    $log.info('showing 50 more watchlist entries');
    var temp = vm.watchlist.filtered.slice(vm.watchlist.active.length, vm.watchlist.active.length + 50);
    Array.prototype.push.apply(vm.watchlist.active, temp);
  };

  /**
   * Filter watchlist
   * @param searchtext
   */
  vm.filterWatchlist = function (searchtext) {
    if (vm.watchlist.original.length === 0) {
      return;
    }

    $log.info('showing first 100 watchlist entries');
    vm.watchlist.filtered = $filter('watchlist')(vm.watchlist.original, vm.config);
    if (typeof searchtext !== 'undefined') {
      vm.watchlist.filtered = $filter('filter')(vm.watchlist.filtered, searchtext);
    }
    var temp = vm.watchlist.filtered.slice(0, 100);
    vm.watchlist.active.length = 0;
    Array.prototype.push.apply(vm.watchlist.active, temp);
    $log.info(vm.watchlist.active.length);
  };
  vm.filterWatchlistDebounced = debounce(vm.filterWatchlist, 250);

  /**
   * Reset watchlist and query it again
   */
  vm.resetWatchlist = function () {
    vm.watchlist.original = [];
    vm.watchlist.filtered = [];
    vm.watchlist.active.length = 0; /* preserve pointer, slow due to GC */
    vm.queryWatchlist();
    vm.saveConfig();
  };

  /**
   * Save user config to local storage
   */
  vm.saveConfig = function() {
    localStorageService.set('config', vm.config);
  };

  /**
   * If logged in, query watchlist.
   */
  vm.queryWatchlist = function () {
    if (authService.isloggedin()) {
      var watchlistQuery = {
        action: 'watchlist',
        access_token: authService.tokens(),
        watchlistperiod: vm.config.watchlistperiod,
        allrev: !vm.config.lastrevonly,
        projects: vm.config.projectsList
      };
      try {
        socket.send(angular.toJson(watchlistQuery));
      } catch(err) {
        // INVALID_STATE_ERR when sockjs is not yet connected
        if (err.message === 'InvalidStateError: The connection has not been established yet') {
          $log.warn('Wachtlist queried before socketjs connected.');
        } else {
          $log.error(err);
        }
      }
    }
  };
}

// Debounce function
// From http://stackoverflow.com/a/13320016 by Pete BD
function debounceService ($timeout, $q) {
  // The service is actually this function, which we call with the func
  // that should be debounced and how long to wait in between calls
  return function debounce(func, wait, immediate) {
    var timeout;
    // Create a deferred object that will be resolved when we need to
    // actually call the func
    var deferred = $q.defer();
    return function() {
      var context = this, args = arguments;
      var later = function() {
        timeout = null;
        if(!immediate) {
          deferred.resolve(func.apply(context, args));
          deferred = $q.defer();
        }
      };
      var callNow = immediate && !timeout;
      if ( timeout ) {
        $timeout.cancel(timeout);
      }
      timeout = $timeout(later, wait);
      if (callNow) {
        deferred.resolve(func.apply(context,args));
        deferred = $q.defer();
      }
      return deferred.promise;
    };
  };
}
