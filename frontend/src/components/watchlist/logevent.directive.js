angular
  .module('crosswatch')
  .directive('watchlistLogevent', watchlistLogevent);

function watchlistLogevent() {
  var directive = {
    link: link,
    templateUrl: 'components/watchlist/logevent.directive.html',
    restrict: 'E'
  };
  return directive;

  function link(scope, element, attrs) {
    /*
     * copy event.logparams properties to event
     */
    for (var prop in scope.event.logparams) {
      if (scope.event.logparams.hasOwnProperty(prop)) {
        if (!(isNumber(prop)) && !(scope.event.hasOwnProperty(prop))) {
          scope.event[prop] = scope.event.logparams[prop];
        }
      }
    }

    /*
     * Rename badly named logparams properties
     */
    if (scope.event.logaction === 'move_prot') {
      scope.event.target_title = scope.event.logparams['0'];
    } else if (scope.event.logtype === 'protect') {
      scope.event.protection_level = scope.event.logparams['0'];
    }

    function isNumber(obj) { return !isNaN(parseFloat(obj)) }
  }
}
