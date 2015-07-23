'use strict';
angular
  .module('crosswatch')
  .service('authService', authService)
  .service('dataService', dataService)
  .factory('debounce', debounceService)
;

function authService (localStorageService) {
  this.isLoggedIn = function () {
    // check if cookie is from latest consumer version
    var version = localStorageService.cookie.get('version');
    if (version !== 1) {
      localStorageService.cookie.clearAll();
      return false;
    }

    return (localStorageService.cookie.get('auth') !== null);
  };

  this.tokens = function () {
    return angular.fromJson(localStorageService.cookie.get('auth').replace(/\\054/g, ','));
  };

  this.user = function () {
    return localStorageService.cookie.get('user');
  };
}

function dataService (socket, authService, localStorageService, $log, $filter, debounce, $q) {
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
   * loading spinner
   */
  vm.watchlist.loading = true;

  /**
   * Array that contains new echo notifications.
   * @type {Array}
   */
  vm.notifications = [];

  /**
   * Initialize user settings
   */
  vm.defaultconfig = {
    /**
     * true: show only latest change
     * false: show all changes
     */
    lastrevonly: true,
    /**
     * Timeperiod for which the watchlist is retrieved in days
     */
    watchlistperiod: 1.5,
    /**
     * Show flags instead of language names
     */
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
    projectsSelected: false,
    /**
     * List of namespaces shown in options list
     */
    namespacesList: ["0", "1", "2", "3", "4", "5", "6", "7", "10", "11", "12", "13", "OTHER"],
    /**
     * Username
     */
    username: "",
    /**
     * Filter out own edits
     */
    hideOwnEdits: false
  };
  // Get config from localstorage or create from defaultconfig
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
   * List of selected namespaces
   */
  vm.config.namespacesSelected = vm.config.namespacesSelected || vm.defaultconfig.namespacesList;
  /**
   * Associative array from project to border color
   */
  vm.config.projectColors = vm.config.projectColors || {};


  var colors = ['pink', 'deep-purple', 'blue', 'cyan', 'green', 'lime', 'orange', 'brown', 'blue-grey'];
  var colorsIndex = 0;

  /**
   * Save user config to local storage
   */
  vm.saveConfig = function() {
    localStorageService.set('config', vm.config);
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

    if (!vm.config.projectColors.hasOwnProperty(project)) {
      vm.config.projectColors[project] = 'project-color-' + colors[colorsIndex];

      colorsIndex += 1;
      if (colorsIndex >= colors.length) {
        colorsIndex = 0;
      }
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

    $log.info('showing first watchlist entries (maximum 100)');
    vm.watchlist.filtered = $filter('watchlist')(vm.watchlist.original, vm.config);
    if (typeof searchtext !== 'undefined') {
      vm.watchlist.filtered = $filter('filter')(vm.watchlist.filtered, searchtext);
    }

    var temp = vm.watchlist.filtered.slice(0, 100);
    vm.watchlist.active.length = 0;
    Array.prototype.push.apply(vm.watchlist.active, temp);
    vm.watchlist.loading = false;
  };
  vm.filterWatchlistDebounced = debounce(vm.filterWatchlist, 250);

  /**
   * Reset watchlist and query it again
   */
  vm.resetWatchlist = function () {
    vm.watchlist.original = [];
    vm.watchlist.filtered = [];
    vm.watchlist.active.length = 0; /* preserve pointer, slow due to GC */
    vm.notifications.length = 0;
    vm.queryWatchlist();
    vm.saveConfig();
  };

  /**
   * Process a new echo entry.
   * @param entry
   */
  vm.addNotificationEntries = function (entry) {
    vm.notifications.push(entry);
  };

  /**
   * Mark all notifications as read.
   */
  vm.markNotificationsRead = function () {
    var notifications = {};
    for (var i=0; i<vm.notifications.length; i++) {
      var not = vm.notifications[i];
      if (!notifications.hasOwnProperty(not.project)) {
        notifications[not.project] = [];
      }

      notifications[not.project].push(not.id);
    }
    var query = {
      action: 'notifications_mark_read',
      access_token: authService.tokens(),
      notifications: notifications
    };
    socket.send(angular.toJson(query));
  };

  /**
   * If logged in, query watchlist.
   */
  vm.queryWatchlist = function () {
    if (authService.isLoggedIn()) {
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

  /**
   * Callbacks with associated request ids
   */
  var callbacks = {};
  var requestId = 0;
  vm.getRequestId = function() {
    return requestId++;
  };

  /**
   * Send requests to sockjs server, returns a promise
   */
  vm.query = function (params) {
    params.request_id = vm.getRequestId();
    params.access_token = authService.tokens();

    var deferred = $q.defer();
    callbacks[params.request_id] = deferred;
    socket.send(angular.toJson(params));
    return deferred.promise.then(function(response) {
      params.response = response;
      return response;
    });
  };

  /**
   * Resolves query promises
   */
  vm.responseHandler = function (data) {
    if (angular.isDefined(callbacks[data.request_id])) {
      var callback = callbacks[data.request_id];
      delete callbacks[data.request_id];
      callback.resolve(data.data);
    } else {
      $log.error("No callback for diff: %o", data);
    }
  };

  /**
   * General data storage
   */
  vm.icons = {};
  vm.icons['wikibooks']   = "//upload.wikimedia.org/wikipedia/commons/f/fa/Wikibooks-logo.svg";
  vm.icons['wiktionary']  = "//upload.wikimedia.org/wikipedia/commons/e/ef/Wikitionary.svg";
  vm.icons['wikiquote']   = "//upload.wikimedia.org/wikipedia/commons/f/fa/Wikiquote-logo.svg";
  vm.icons['wikipedia']   = "//upload.wikimedia.org/wikipedia/commons/8/80/Wikipedia-logo-v2.svg";
  vm.icons['wikinews']    = "//upload.wikimedia.org/wikipedia/commons/2/24/Wikinews-logo.svg";
  vm.icons['wikivoyage']  = "//upload.wikimedia.org/wikipedia/commons/8/8a/Wikivoyage-logo.svg";
  vm.icons['wikisource']  = "//upload.wikimedia.org/wikipedia/commons/4/4c/Wikisource-logo.svg";
  vm.icons['wikiversity'] = "//upload.wikimedia.org/wikipedia/commons/9/91/Wikiversity-logo.svg";
  vm.icons['foundation']  = "//upload.wikimedia.org/wikipedia/commons/c/c4/Wikimedia_Foundation_RGB_logo_with_text.svg";
  vm.icons['mediawiki']   = "//upload.wikimedia.org/wikipedia/commons/3/3d/Mediawiki-logo.png";
  vm.icons['meta']        = "//upload.wikimedia.org/wikipedia/commons/7/75/Wikimedia_Community_Logo.svg";
  vm.icons['wikidata']    = "//upload.wikimedia.org/wikipedia/commons/f/ff/Wikidata-logo.svg";
  vm.icons['commons']     = "//upload.wikimedia.org/wikipedia/commons/4/4a/Commons-logo.svg";
  vm.icons['species']     = "//upload.wikimedia.org/wikipedia/en/b/bf/Wikispecies-logo-35px.png";
  vm.icons['incubator']   = "//upload.wikimedia.org/wikipedia/commons/e/e3/Incubator-logo.svg";
  vm.icons['test']        = "//upload.wikimedia.org/wikipedia/commons/4/4a/Wikipedia_logo_v2_%28black%29.svg";

  vm.flags = ["ad", "ae", "af", "ag", "ai", "al", "am", "an", "ao", "ar", "as", "at", "au", "aw", "ax", "az", "ba", "bb", "bd", "be", "bf", "bg", "bh", "bi", "bj", "bm", "bn", "bo", "br", "bs", "bt", "bv", "bw", "by", "bz", "ca", "cc", "cd", "cf", "cg", "ch", "ci", "ck", "cl", "cm", "cn", "co", "cr", "cs", "cu", "cv", "cx", "cy", "cz", "da", "de", "dj", "dk", "dm", "do", "dz", "ec", "ee", "eg", "eh", "en", "er", "es", "et", "fam", "fi", "fj", "fk", "fm", "fo", "fr", "ga", "gb", "gd", "ge", "gf", "gh", "gi", "gl", "gm", "gn", "gp", "gq", "gr", "gs", "gt", "gu", "gw", "gy", "he", "hk", "hm", "hn", "hr", "ht", "hu", "id", "ie", "il", "in", "io", "iq", "ir", "is", "it", "jm", "jo", "jp", "ke", "kg", "kh", "ki", "km", "kn", "kp", "kr", "kw", "ky", "kz", "la", "lb", "lc", "li", "lk", "lr", "ls", "lt", "lu", "lv", "ly", "ma", "mc", "md", "me", "mg", "mh", "mk", "ml", "mm", "mn", "mo", "mp", "mq", "mr", "ms", "mt", "mu", "mv", "mw", "mx", "my", "mz", "na", "nc", "ne", "nf", "ng", "ni", "nl", "no", "np", "nr", "nu", "nz", "om", "pa", "pe", "pf", "pg", "ph", "pk", "pl", "pm", "pn", "pr", "ps", "pt", "pw", "py", "qa", "re", "ro", "rs", "ru", "rw", "sa", "sb", "scotland", "sc", "sd", "se", "sg", "sh", "si", "sj", "sk", "sl", "sm", "sn", "so", "sr", "st", "sv", "sy", "sz", "tc", "td", "tf", "tg", "th", "tj", "tk", "tl", "tm", "tn", "to", "tr", "tt", "tv", "tw", "tz", "ua", "ug", "um", "us", "uy", "uz", "va", "vc", "ve", "vg", "vi", "vn", "vu", "wales", "wf", "ws", "ye", "yt", "za", "zh", "zm", "zw"];

  vm.flagurl = function (lang) {
    if (vm.flags.indexOf(lang) >= 0) {
      return "assets/images/flags/png/" + lang + ".png";
    } else {
      return false;
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
