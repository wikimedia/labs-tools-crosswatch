angular
  .module('crosswatch')
  .directive('comment', comment);

function comment ($sanitize) {
  var directive = {
    link: link,
    restrict: 'E'
  };
  return directive;

  function link (scope, element, attrs) {
    var html = scope.event.parsedcomment;
    element.html($sanitize(html));
    element.find('a').bind('click', function (e) {
      e.stopPropagation();
    });
  }
}
