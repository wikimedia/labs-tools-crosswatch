angular
  .module('crosswatch')
  .directive('watchlistEdit', watchlistEdit);

function watchlistEdit() {
  var directive = {
    link: link,
    templateUrl: 'components/watchlist/edit.directive.html',
    restrict: 'EA'
  };
  return directive;

  function link(scope, element, attrs) {
    /* */
  }
}
