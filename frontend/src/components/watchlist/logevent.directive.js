angular
  .module('crosswatch')
  .directive('watchlistLogevent', watchlistLogevent);

function watchlistLogevent() {
  var directive = {
    link: link,
    templateUrl: 'components/watchlist/logevent.directive.html',
    restrict: 'EA'
  };
  return directive;

  function link(scope, element, attrs) {
    /* */
  }
}
