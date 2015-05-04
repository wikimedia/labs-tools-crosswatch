angular
  .module('crosswatch')
  .directive('watchlistEntry', watchlistEntry);

function watchlistEntry() {
  var directive = {
    link: link,
    templateUrl: 'components/watchlist/entry.directive.html',
    restrict: 'EA'
  };
  return directive;

  function link(scope, element, attrs) {
    /* */
  }
}
