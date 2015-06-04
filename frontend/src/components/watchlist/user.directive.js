angular
  .module('crosswatch')
  .directive('user', user);

function user() {
  var directive = {
    link: link,
    scope: true,
    template: '<a href="{{::event.projecturl}}/wiki/User:{{::event.user | urlEncode}}"  target="_blank">{{::event.user}}</a>',
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
