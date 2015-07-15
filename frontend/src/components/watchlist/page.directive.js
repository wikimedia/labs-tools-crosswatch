angular
  .module('crosswatch')
  .directive('page', page);

function page() {
  var directive = {
    link: link,
    scope: true,
    template: '<a stop-event href="{{::event.projecturl}}/wiki/{{::title | urlEncode}}"  target="_blank">{{::title}}</a> ' +
    '<span ng-if="event.clicked">' +
    '(<a stop-event href="{{::event.projecturl}}/w/index.php?title={{::title | urlEncode}}&action=history" target="_blank" translate="HISTORY"></a>)' +
    '</span>&#32;',
    restrict: 'E'
  };
  return directive;

  function link(scope, element, attrs) {
    if (typeof attrs.title !== 'undefined') {
      scope.title = attrs.title;
    } else {
      scope.title = scope.event.title;
    }
  }
}
