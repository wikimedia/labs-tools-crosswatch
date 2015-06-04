angular
  .module('crosswatch')
  .directive('page', page);

function page() {
  var directive = {
    link: link,
    scope: true,
    template: '<a href="{{::event.projecturl}}/wiki/{{::event.title | urlEncode}}"  target="_blank">{{::event.title}}</a>',
    restrict: 'E'
  };
  return directive;

  function link(scope, element, attrs) {
    if (typeof attrs.title !== 'undefined') {
      scope.event.title = attrs.title;
    }
  }
}
