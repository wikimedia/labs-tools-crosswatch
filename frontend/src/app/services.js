'use strict';
angular
  .module('crosswatch')
  .service('authService', authService)
  .service('dataService', dataService)
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

function dataService (socket, authService, localStorageService, $log) {
  var vm = this;

  /**
   * Array that contains all watchlist entries.
   * @type {Array}
   */
  vm.watchlist = [];

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
    vm.watchlist.push.apply(vm.watchlist, entries);
    var project = entries[0].project;
    if (vm.config.projectsList.indexOf(project) === -1) {
      vm.config.projectsList.push(project);
      vm.config.projectsSelected.push(project);
      vm.saveConfig();
    }
  };

  /**
   * Reset watchlist and query it again
   */
  vm.resetWatchlist = function () {
    vm.watchlist.length = 0;
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
