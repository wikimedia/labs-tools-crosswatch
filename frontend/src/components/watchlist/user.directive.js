angular
  .module('crosswatch')
  .directive('user', user);

function user() {
  var directive = {
    link: link,
    scope: true,
    template: '<a stop-event href="{{::event.projecturl}}/wiki/User:{{::user | urlEncode}}" target="_blank">{{::user}}</a> ' +
    '<span ng-if="event.clicked">' +
    '(<a stop-event href="{{::event.projecturl}}/wiki/Special:Contributions/{{::user | urlEncode}}" target="_blank" translate="CONTRIBS"></a>)' +
    '</span>',
    restrict: 'E'
  };
  return directive;

  function link(scope, element, attrs) {
    if (typeof attrs.name !== 'undefined') {
      scope.user = attrs.name;
    } else {
      scope.user = scope.event.user;
    }
  }
}
