angular
  .module('crosswatch')
  .directive('user', user);

function user() {
  var directive = {
    link: link,
    scope: true,
    template: '<a href="{{::event.projecturl}}/wiki/User:{{::event.user | urlEncode}}"  target="_blank">{{::event.user}}</a> ' +
    '<span ng-if="event.clicked">' +
    '(<a href="{{::event.projecturl}}/wiki/Special:Contributions/{{::event.user | urlEncode}}" translate="CONTRIBS"></a>)' +
    '</span>',
    restrict: 'E'
  };
  return directive;

  function link(scope, element, attrs) {
    if (typeof attrs.name !== 'undefined') {
      scope.event.user = attrs.name;
    }

    scope.event.user = scope.event.user.replace("User:", "");
  }
}
