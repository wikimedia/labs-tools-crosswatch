angular
  .module('crosswatch')
  .directive('watchlistEntry', watchlistEntry);

function watchlistEntry() {
  var directive = {
    scope: true,
    templateUrl: 'components/watchlist/entry.directive.html',
    restrict: 'EA'
  };
  return directive;
}
