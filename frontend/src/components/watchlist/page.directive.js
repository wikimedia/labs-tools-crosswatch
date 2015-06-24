angular
  .module('crosswatch')
  .directive('page', page);

function page() {
  var directive = {
    link: link,
    scope: true,
    template: '<a href="{{::event.projecturl}}/wiki/{{::event.title | urlEncode}}"  target="_blank">{{::event.title}}</a> ' +
    '<span ng-if="event.clicked">' +
    '(<a href="{{::event.projecturl}}/w/index.php?title={{::event.title | urlEncode}}&action=history" translate="HISTORY"></a>)' +
    '</span>',
    restrict: 'E'
  };
  return directive;

  function link(scope, element, attrs) {
    if (typeof attrs.title !== 'undefined') {
      scope.event.title = attrs.title;
    }
  }
}
