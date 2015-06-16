angular
  .module('crosswatch')
  .directive('watchlistEntry', watchlistEntry);

function watchlistEntry() {
  var directive = {
    templateUrl: 'components/watchlist/entry.directive.html',
    restrict: 'EA'
  };
  return directive;
}
