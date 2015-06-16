'use strict';
angular
  .module('crosswatch')
  .filter('urlEncode', urlEncodeFilter)
  .filter('list', listFilter)
  .filter('watchlist', watchlistFilter)
  .filter('projects', projectsFilter)
  .filter('editflags', editflagsFilter)
;

/**
 * Filter for encoding strings for use in URL query strings
 */
function urlEncodeFilter () {
  return window.encodeURIComponent;
}

/**
 * Formats lists:
 *   ["a", "b", "c"] -> "(a, b, c)"
 *   [] -> "(–)"
 */
function listFilter () {
  return function (list) {
    list = list || [];
    var result = list.join(', ');
    if (result.length === 0) {
      result = "–";
    }
    result = "(" + result + ")";

    return result;
  }
}

/**
 * combined filter for watchlist
 */
function watchlistFilter () {
  return function (items, config) {
    return items.filter(filter, config);
  };

  function filter (item) {
    var bool = projectsFilter(item, this.projectsSelected);

    if (bool) {
      bool = editsflagsFilter(item, this.editflags);
    }
    return bool;
  }

  /**
   * Filters watchlist based on selected / blacklisted wikis
   */
  function projectsFilter (item, projects) {
    return (projects.indexOf(item.project) > -1);
  }

  /**
   * Filters watchlist based on editflags (minor, bot, registered)
   */
  function editsflagsFilter (item, flags) {
    if (item.type === 'log') {
      return true;
    }
    var minor = flags.minor || !item.minor;
    var bot = flags.bot || !item.bot;
    var anon = flags.anon || !(item.anon === "");
    var registered = flags.registered || !(item.userid !== 0);
    return (minor && bot && anon && registered);
  }
}

/**
 * Filters watchlist based on selected / blacklisted wikis
 */
function projectsFilter () {
  return function (items, projects) {
    return items.filter(filter, projects)
  };

  function filter (item) {
    return (this.indexOf(item.project) > -1);
  }
}

/**
 * Filters watchlist based on editflags (minor, bot, registered)
 */
function editflagsFilter () {
  return function (items, flags) {
    return items.filter(filter, flags)
  };

  function filter (item) {
    if (item.type === 'log') {
      return true;
    }
    var minor = this.minor || !item.minor;
    var bot = this.bot || !item.bot;
    var anon = this.anon || !(item.anon === "");
    var registered = this.registered || !(item.userid !== 0);
    return (minor && bot && anon && registered);
  }
}
