'use strict';
angular
  .module('crosswatch')
  .filter('urlEncode', urlEncodeFilter)
  .filter('list', listFilter)
  .filter('watchlist', watchlistFilter)
  .filter('projectList', projectsFilter)
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
    var bool = projectsFilterFunc(item, this.projectsSelected);

    if (bool) {
      bool = editsflagsFilterFunc(item, this.editflags);
    }

    if (bool) {
      bool = namespaceFilterFunc(item, this.namespacesSelected, this.namespacesList)
    }

    if (bool && this.hideOwnEdits) {
      bool = usernameFilterFunc(item, this.username)
    }
    return bool;
  }
}

/**
 * Filters watchlist based on selected / blacklisted wikis
 */
function projectsFilterFunc (item, projects) {
  return (projects.indexOf(item.project) > -1);
}

/**
 * Filters watchlist based on editflags (minor, bot, registered)
 */
function editsflagsFilterFunc (item, flags) {
  if (item.type === 'log') {
    return true;
  }
  var minor = flags.minor || !item.minor;
  var bot = flags.bot || !item.bot;
  var anon = flags.anon || !(item.anon === "");
  var registered = flags.registered || !(item.userid !== 0);
  return (minor && bot && anon && registered);
}

/**
 * Filter watchlist based on namespace
 */
function namespaceFilterFunc (item, namespaces, namespacesList) {
  if (namespaces.indexOf(item.ns.toString()) > -1) {
    return true;
  } else if ((namespaces.indexOf("OTHER") > -1) && (namespacesList.indexOf(item.ns.toString())) === -1) {
    return true;
  }
  return false;
}

/**
 * Filter out own edits
 */
function usernameFilterFunc (item, username) {
  return item.user !== username;
}

function projectsFilter () {
  return function (items, config) {
    return items.filter(projectListFilterFunc, config)
  };
}

function projectListFilterFunc (items) {
  return (this.projectsSelected.indexOf(items) > -1);
}
